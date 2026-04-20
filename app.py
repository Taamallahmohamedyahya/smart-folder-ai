import os
import re
import json
import shutil
import hashlib
import mimetypes
import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


CATEGORY_MAP = {
    "Images": {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg"},
    "PDFs": {".pdf"},
    "Documents": {".doc", ".docx", ".txt", ".rtf", ".odt", ".md"},
    "Spreadsheets": {".xls", ".xlsx", ".csv"},
    "Presentations": {".ppt", ".pptx"},
    "Code": {".py", ".js", ".ts", ".java", ".c", ".cpp", ".html", ".css", ".json", ".go", ".rs", ".php", ".rb", ".swift", ".kt", ".sql", ".sh"},
    "Archives": {".zip", ".rar", ".7z", ".tar", ".gz"},
    "Audio": {".mp3", ".wav", ".aac", ".flac", ".ogg", ".m4a"},
    "Video": {".mp4", ".mkv", ".mov", ".avi", ".webm"},
}


SMART_RULES = {
    "Invoices": [r"invoice", r"receipt", r"bill", r"payment", r"purchase", r"order"],
    "Resume": [r"resume", r"cv"],
    "Taxes": [r"tax", r"irs", r"vat", r"declaration"],
    "Banking": [r"bank", r"statement", r"account"],
    "Contracts": [r"contract", r"agreement", r"nda", r"terms"],
    "School": [r"assignment", r"course", r"lecture", r"homework", r"exam"],
    "Projects": [r"project", r"spec", r"roadmap", r"plan", r"milestone"],
    "Screenshots": [r"screenshot", r"screen shot", r"capture"],
    "Photos": [r"img", r"photo", r"dsc_", r"pics?"],
}


EXTENSION_RENAME_HINTS = {
    ".pdf": "document",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".csv": "spreadsheet",
    ".xlsx": "spreadsheet",
    ".docx": "document",
    ".py": "script",
    ".js": "script",
}


def sha256_file(path: Path, chunk_size: int = 65536) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)
    return hasher.hexdigest()


def safe_slug(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "file"


class FileOrganizerApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Smart Folder Organizer AI")
        self.root.geometry("1180x760")
        self.root.minsize(980, 620)

        self.selected_folder = tk.StringVar()
        self.status_var = tk.StringVar(value="Choose a folder to analyze.")
        self.move_files_var = tk.BooleanVar(value=False)
        self.detect_duplicates_var = tk.BooleanVar(value=True)
        self.smart_label_var = tk.BooleanVar(value=True)
        self.suggest_rename_var = tk.BooleanVar(value=True)

        self.files_data = []
        self.report_lines = []
        self.preview_plan = []

        self._build_style()
        self._build_ui()

    def _build_style(self):
        self.root.configure(bg="#0f172a")
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure("Root.TFrame", background="#0f172a")
        style.configure("Card.TFrame", background="#111827")
        style.configure("Title.TLabel", background="#0f172a", foreground="#f8fafc", font=("Segoe UI", 18, "bold"))
        style.configure("Muted.TLabel", background="#0f172a", foreground="#94a3b8", font=("Segoe UI", 10))
        style.configure("CardTitle.TLabel", background="#111827", foreground="#e5e7eb", font=("Segoe UI", 11, "bold"))
        style.configure("TLabel", font=("Segoe UI", 10))
        style.configure("TButton", font=("Segoe UI", 10, "bold"), padding=8)
        style.configure("TCheckbutton", background="#0f172a", foreground="#e5e7eb", font=("Segoe UI", 10))
        style.configure("Treeview", rowheight=28, font=("Segoe UI", 10), fieldbackground="#ffffff")
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))

    def _build_ui(self):
        container = ttk.Frame(self.root, padding=18, style="Root.TFrame")
        container.pack(fill="both", expand=True)

        header = ttk.Frame(container, style="Root.TFrame")
        header.pack(fill="x", pady=(0, 14))
        ttk.Label(header, text="Smart Folder Organizer AI", style="Title.TLabel").pack(anchor="w")
        ttk.Label(header, text="Analyze, classify, preview, and organize files with smarter labeling.", style="Muted.TLabel").pack(anchor="w", pady=(4, 0))

        top_card = ttk.Frame(container, padding=14, style="Card.TFrame")
        top_card.pack(fill="x", pady=(0, 14))

        row1 = ttk.Frame(top_card, style="Card.TFrame")
        row1.pack(fill="x")
        ttk.Label(row1, text="Folder", style="CardTitle.TLabel").pack(side="left")
        ttk.Entry(row1, textvariable=self.selected_folder, font=("Segoe UI", 10)).pack(side="left", fill="x", expand=True, padx=10)
        ttk.Button(row1, text="Browse", command=self.browse_folder).pack(side="left")
        ttk.Button(row1, text="Analyze", command=self.start_scan).pack(side="left", padx=(10, 0))

        row2 = ttk.Frame(top_card, style="Card.TFrame")
        row2.pack(fill="x", pady=(12, 0))
        ttk.Checkbutton(row2, text="Detect duplicates", variable=self.detect_duplicates_var).pack(side="left", padx=(0, 14))
        ttk.Checkbutton(row2, text="Smart AI labeling", variable=self.smart_label_var).pack(side="left", padx=(0, 14))
        ttk.Checkbutton(row2, text="Suggest cleaner names", variable=self.suggest_rename_var).pack(side="left", padx=(0, 14))
        ttk.Checkbutton(row2, text="Apply changes to folders", variable=self.move_files_var).pack(side="left")

        content = ttk.Panedwindow(container, orient="horizontal")
        content.pack(fill="both", expand=True)

        left = ttk.Frame(content, padding=12, style="Card.TFrame")
        right = ttk.Frame(content, padding=12, style="Card.TFrame")
        content.add(left, weight=3)
        content.add(right, weight=2)

        ttk.Label(left, text="Analysis Results", style="CardTitle.TLabel").pack(anchor="w", pady=(0, 8))
        columns = ("name", "category", "smart_label", "rename", "duplicate")
        self.tree = ttk.Treeview(left, columns=columns, show="headings")
        self.tree.heading("name", text="File")
        self.tree.heading("category", text="Type")
        self.tree.heading("smart_label", text="Smart Label")
        self.tree.heading("rename", text="Suggested Name")
        self.tree.heading("duplicate", text="Duplicate")
        self.tree.column("name", width=250)
        self.tree.column("category", width=100, anchor="center")
        self.tree.column("smart_label", width=130, anchor="center")
        self.tree.column("rename", width=250)
        self.tree.column("duplicate", width=90, anchor="center")

        tree_scroll = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")

        upper_right = ttk.Frame(right, style="Card.TFrame")
        upper_right.pack(fill="both", expand=True)
        ttk.Label(upper_right, text="Preview Plan", style="CardTitle.TLabel").pack(anchor="w", pady=(0, 8))
        self.preview_text = tk.Text(upper_right, wrap="word", height=12, bg="#0b1220", fg="#e5e7eb", insertbackground="#e5e7eb", relief="flat", font=("Consolas", 10))
        self.preview_text.pack(fill="both", expand=True)

        lower_right = ttk.Frame(right, style="Card.TFrame")
        lower_right.pack(fill="both", expand=True, pady=(12, 0))
        ttk.Label(lower_right, text="Summary Report", style="CardTitle.TLabel").pack(anchor="w", pady=(0, 8))
        self.report_text = tk.Text(lower_right, wrap="word", height=12, bg="#0b1220", fg="#e5e7eb", insertbackground="#e5e7eb", relief="flat", font=("Consolas", 10))
        self.report_text.pack(fill="both", expand=True)

        footer = ttk.Frame(container, style="Root.TFrame")
        footer.pack(fill="x", pady=(14, 0))
        ttk.Label(footer, textvariable=self.status_var, style="Muted.TLabel").pack(side="left")
        ttk.Button(footer, text="Export Report", command=self.export_report).pack(side="right")

    def browse_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.selected_folder.set(folder)

    def start_scan(self):
        folder = self.selected_folder.get().strip()
        if not folder:
            messagebox.showwarning("No folder selected", "Please choose a folder first.")
            return
        if not os.path.isdir(folder):
            messagebox.showerror("Invalid folder", "The selected path is not a valid folder.")
            return

        self.status_var.set("Analyzing files and building a preview plan...")
        self._clear_results()
        threading.Thread(target=self.scan_folder, args=(Path(folder),), daemon=True).start()

    def _clear_results(self):
        self.files_data.clear()
        self.report_lines.clear()
        self.preview_plan.clear()
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.preview_text.delete("1.0", tk.END)
        self.report_text.delete("1.0", tk.END)

    def categorize_file(self, file_path: Path) -> str:
        ext = file_path.suffix.lower()
        for category, extensions in CATEGORY_MAP.items():
            if ext in extensions:
                return category

        mime_type, _ = mimetypes.guess_type(str(file_path))
        if mime_type:
            if mime_type.startswith("image"):
                return "Images"
            if mime_type.startswith("audio"):
                return "Audio"
            if mime_type.startswith("video"):
                return "Video"
            if mime_type.startswith("text"):
                return "Documents"
        return "Others"

    def smart_label_file(self, file_path: Path, category: str) -> str:
        name = file_path.stem.lower()
        for label, patterns in SMART_RULES.items():
            for pattern in patterns:
                if re.search(pattern, name):
                    return label

        if category == "PDFs":
            return "Reference"
        if category == "Images":
            return "Media"
        if category == "Code":
            return "Development"
        if category == "Documents":
            return "Notes"
        return category

    def suggest_name(self, file_path: Path, smart_label: str) -> str:
        ext = file_path.suffix.lower()
        original = file_path.stem
        cleaned = re.sub(r"[_\-]+", " ", original)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        if len(cleaned) < 4 or cleaned.lower() in {"img", "scan", "doc", "file", "new"}:
            hint = EXTENSION_RENAME_HINTS.get(ext, "file")
            cleaned = f"{smart_label} {hint}"

        suggested = safe_slug(cleaned)
        return f"{suggested}{ext}"

    def unique_destination(self, destination: Path) -> Path:
        if not destination.exists():
            return destination
        stem = destination.stem
        suffix = destination.suffix
        counter = 1
        while True:
            candidate = destination.with_name(f"{stem}_{counter}{suffix}")
            if not candidate.exists():
                return candidate
            counter += 1

    def scan_folder(self, folder: Path):
        category_counts = {}
        label_counts = {}
        duplicate_map = {}
        duplicate_files = []
        total_files = 0
        moved_files = 0

        try:
            entries = [p for p in folder.iterdir() if p.is_file()]
        except Exception as e:
            self.root.after(0, lambda: self.status_var.set(f"Error reading folder: {e}"))
            return

        for file_path in entries:
            total_files += 1
            category = self.categorize_file(file_path)
            smart_label = self.smart_label_file(file_path, category) if self.smart_label_var.get() else category
            suggested_name = self.suggest_name(file_path, smart_label) if self.suggest_rename_var.get() else file_path.name
            is_duplicate = False

            if self.detect_duplicates_var.get():
                try:
                    file_hash = sha256_file(file_path)
                    if file_hash in duplicate_map:
                        is_duplicate = True
                        duplicate_files.append(file_path.name)
                    else:
                        duplicate_map[file_hash] = file_path
                except Exception:
                    pass

            target_folder = folder / smart_label if self.move_files_var.get() else folder
            target_path = self.unique_destination(target_folder / suggested_name)

            self.preview_plan.append(f"{file_path.name}  ->  {target_path.name if target_folder == folder else str(target_path.relative_to(folder))}")

            if self.move_files_var.get():
                try:
                    target_folder.mkdir(exist_ok=True)
                    shutil.move(str(file_path), str(target_path))
                    moved_files += 1
                except Exception:
                    pass

            category_counts[category] = category_counts.get(category, 0) + 1
            label_counts[smart_label] = label_counts.get(smart_label, 0) + 1
            self.files_data.append({
                "name": file_path.name,
                "category": category,
                "smart_label": smart_label,
                "rename": suggested_name,
                "duplicate": "Yes" if is_duplicate else "No",
            })

        self.report_lines.append(f"Scanned folder: {folder}")
        self.report_lines.append(f"Total files analyzed: {total_files}")
        self.report_lines.append("")
        self.report_lines.append("Detected file types:")
        for category, count in sorted(category_counts.items()):
            self.report_lines.append(f"- {category}: {count}")

        self.report_lines.append("")
        self.report_lines.append("Smart labels:")
        for label, count in sorted(label_counts.items()):
            self.report_lines.append(f"- {label}: {count}")

        self.report_lines.append("")
        self.report_lines.append(f"Duplicates found: {len(duplicate_files)}")
        for name in duplicate_files[:20]:
            self.report_lines.append(f"- {name}")
        if len(duplicate_files) > 20:
            self.report_lines.append(f"...and {len(duplicate_files) - 20} more")

        if self.move_files_var.get():
            self.report_lines.append("")
            self.report_lines.append(f"Files reorganized: {moved_files}")

        self.root.after(0, self.update_ui_after_scan)

    def update_ui_after_scan(self):
        for item in self.files_data:
            self.tree.insert("", "end", values=(item["name"], item["category"], item["smart_label"], item["rename"], item["duplicate"]))

        self.preview_text.delete("1.0", tk.END)
        self.preview_text.insert("1.0", "\n".join(self.preview_plan) if self.preview_plan else "No actions planned.")

        self.report_text.delete("1.0", tk.END)
        self.report_text.insert("1.0", "\n".join(self.report_lines))
        self.status_var.set("Analysis complete.")

    def export_report(self):
        if not self.report_lines:
            messagebox.showinfo("Nothing to export", "Run an analysis first.")
            return

        filepath = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt"), ("JSON Files", "*.json")],
            title="Save report as"
        )
        if not filepath:
            return

        try:
            if filepath.lower().endswith(".json"):
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump({
                        "report": self.report_lines,
                        "preview_plan": self.preview_plan,
                        "files": self.files_data,
                    }, f, indent=2)
            else:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write("\n".join(self.report_lines))
            messagebox.showinfo("Exported", f"Report saved to:\n{filepath}")
        except Exception as e:
            messagebox.showerror("Export failed", str(e))


if __name__ == "__main__":
    root = tk.Tk()
    app = FileOrganizerApp(root)
    root.mainloop()
