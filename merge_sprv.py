"""
SPRV Merge Tool — Tkinter UI

Hash-based dedup merge for two server_privilege.sprv files.
Builds hash tables (SHA-256 of canonical JSON) for O(1) lookups,
then displays a diff view with color-coded categories before writing.
"""

import json
import hashlib
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from dataclasses import dataclass, field

SCRIPT_DIR = Path(__file__).parent
DEFAULT_A = SCRIPT_DIR / "HH_server_privilege" / "server_privilege.sprv"
DEFAULT_B = SCRIPT_DIR / "server_privilege" / "server_privilege.sprv"
DEFAULT_OUT = SCRIPT_DIR / "merged_server_privilege.sprv"

# ── Core hashing / loading ────────────────────────────────────────────────────

def entry_hash(entry: dict) -> str:
    canonical = json.dumps(entry, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load_sprv(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class SectionDiff:
    """Pre-computed hash tables and set categories for one section."""
    hash_a: dict[str, dict] = field(default_factory=dict)
    hash_b: dict[str, dict] = field(default_factory=dict)
    common: set[str] = field(default_factory=set)
    only_a: set[str] = field(default_factory=set)
    only_b: set[str] = field(default_factory=set)


def build_hash_table(entries: list[dict]) -> dict[str, dict]:
    table: dict[str, dict] = {}
    for e in entries:
        table[entry_hash(e)] = e
    return table


def compute_diff(list_a: list[dict], list_b: list[dict]) -> SectionDiff:
    ha = build_hash_table(list_a)
    hb = build_hash_table(list_b)
    keys_a = set(ha.keys())
    keys_b = set(hb.keys())
    return SectionDiff(
        hash_a=ha,
        hash_b=hb,
        common=keys_a & keys_b,
        only_a=keys_a - keys_b,
        only_b=keys_b - keys_a,
    )


# ── Palette ───────────────────────────────────────────────────────────────────

BG           = "#1e1e2e"
BG_LIGHTER   = "#2a2a3d"
FG           = "#cdd6f4"
FG_DIM       = "#7f849c"
ACCENT       = "#89b4fa"
GREEN        = "#a6e3a1"
GREEN_BG     = "#1a2e1a"
RED          = "#f38ba8"
RED_BG       = "#2e1a1a"
YELLOW       = "#f9e2af"
SURFACE      = "#313244"
OVERLAY      = "#45475a"
BORDER       = "#585b70"


# ── Application ───────────────────────────────────────────────────────────────

class MergeTool(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SPRV Merge Tool")
        self.geometry("1100x750")
        self.minsize(900, 600)
        self.configure(bg=BG)

        self.path_a: Path | None = None
        self.path_b: Path | None = None
        self.data_a: dict | None = None
        self.data_b: dict | None = None
        self.roles_diff: SectionDiff | None = None
        self.bans_diff: SectionDiff | None = None
        self.active_section = "roles"
        self.active_filter = "all"
        self.search_query = ""
        self.sort_col: str | None = None
        self.sort_reverse = False

        self._build_styles()
        self._build_menu()
        self._build_stats_bar()
        self._build_tabs_and_filters()
        self._build_search_bar()
        self._build_treeview()
        self._build_detail_panel()
        self._build_bottom_bar()

        self._try_autoload()

    # ── Styles ────────────────────────────────────────────────────────────

    def _build_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")

        style.configure(".", background=BG, foreground=FG, fieldbackground=BG,
                         borderwidth=0, font=("Segoe UI", 10))
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=FG)
        style.configure("TButton", background=SURFACE, foreground=FG,
                         padding=(12, 6), font=("Segoe UI", 10))
        style.map("TButton",
                   background=[("active", OVERLAY)],
                   foreground=[("active", FG)])

        style.configure("Active.TButton", background=ACCENT, foreground=BG,
                         font=("Segoe UI", 10, "bold"))
        style.map("Active.TButton",
                   background=[("active", "#74a8e8")],
                   foreground=[("active", BG)])

        style.configure("Tab.TButton", background=SURFACE, foreground=FG,
                         padding=(16, 6), font=("Segoe UI", 10, "bold"))
        style.map("Tab.TButton",
                   background=[("active", OVERLAY)])
        style.configure("TabActive.TButton", background=ACCENT, foreground=BG,
                         padding=(16, 6), font=("Segoe UI", 10, "bold"))
        style.map("TabActive.TButton",
                   background=[("active", "#74a8e8")],
                   foreground=[("active", BG)])

        style.configure("Apply.TButton", background="#40a02b", foreground="#ffffff",
                         padding=(16, 8), font=("Segoe UI", 11, "bold"))
        style.map("Apply.TButton",
                   background=[("active", "#38912a")],
                   foreground=[("active", "#ffffff")])

        style.configure("Treeview",
                         background=BG_LIGHTER, foreground=FG,
                         fieldbackground=BG_LIGHTER, rowheight=26,
                         font=("Consolas", 10))
        style.configure("Treeview.Heading",
                         background=SURFACE, foreground=ACCENT,
                         font=("Segoe UI", 10, "bold"))
        style.map("Treeview",
                   background=[("selected", OVERLAY)],
                   foreground=[("selected", FG)])

        style.configure("Stat.TLabel", font=("Segoe UI", 10), foreground=FG_DIM)
        style.configure("StatValue.TLabel", font=("Consolas", 10, "bold"), foreground=FG)
        style.configure("Title.TLabel", font=("Segoe UI", 13, "bold"), foreground=ACCENT)

    # ── Menu ──────────────────────────────────────────────────────────────

    def _build_menu(self):
        menubar = tk.Menu(self, bg=SURFACE, fg=FG, activebackground=OVERLAY,
                          activeforeground=FG, borderwidth=0)
        file_menu = tk.Menu(menubar, tearoff=0, bg=SURFACE, fg=FG,
                            activebackground=OVERLAY, activeforeground=FG)
        file_menu.add_command(label="Load File A …", command=self._pick_file_a)
        file_menu.add_command(label="Load File B …", command=self._pick_file_b)
        file_menu.add_separator()
        file_menu.add_command(label="Save Merged …", command=self._save_merged)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.destroy)
        menubar.add_cascade(label="File", menu=file_menu)
        self.config(menu=menubar)

    # ── Stats bar ─────────────────────────────────────────────────────────

    def _build_stats_bar(self):
        frame = ttk.Frame(self, padding=(12, 8))
        frame.pack(fill="x")

        ttk.Label(frame, text="SPRV Merge Tool", style="Title.TLabel").pack(anchor="w")

        row_a = ttk.Frame(frame)
        row_a.pack(fill="x", pady=(4, 0))
        ttk.Button(row_a, text="Browse A …", command=self._pick_file_a).pack(side="left", padx=(0, 8))
        self.lbl_path_a = ttk.Label(row_a, text="File A: (not loaded)", style="Stat.TLabel")
        self.lbl_path_a.pack(side="left", fill="x")

        row_b = ttk.Frame(frame)
        row_b.pack(fill="x", pady=(2, 0))
        ttk.Button(row_b, text="Browse B …", command=self._pick_file_b).pack(side="left", padx=(0, 8))
        self.lbl_path_b = ttk.Label(row_b, text="File B: (not loaded)", style="Stat.TLabel")
        self.lbl_path_b.pack(side="left", fill="x")

        sep = ttk.Separator(frame, orient="horizontal")
        sep.pack(fill="x", pady=(6, 2))

        row = ttk.Frame(frame)
        row.pack(fill="x")
        self.lbl_roles_stats = ttk.Label(row, text="Roles: —", style="StatValue.TLabel")
        self.lbl_roles_stats.pack(side="left", padx=(0, 24))
        self.lbl_bans_stats = ttk.Label(row, text="Bans: —", style="StatValue.TLabel")
        self.lbl_bans_stats.pack(side="left")

    # ── Tab selector + filters ────────────────────────────────────────────

    def _build_tabs_and_filters(self):
        frame = ttk.Frame(self, padding=(12, 4))
        frame.pack(fill="x")

        tabs = ttk.Frame(frame)
        tabs.pack(side="left")
        self.btn_roles = ttk.Button(tabs, text="Roles", command=lambda: self._set_section("roles"))
        self.btn_roles.pack(side="left", padx=(0, 4))
        self.btn_bans = ttk.Button(tabs, text="Bans", command=lambda: self._set_section("bans"))
        self.btn_bans.pack(side="left")

        filters = ttk.Frame(frame)
        filters.pack(side="right")
        ttk.Label(filters, text="Filter:", style="Stat.TLabel").pack(side="left", padx=(0, 6))
        self.filter_buttons: dict[str, ttk.Button] = {}
        for filt in ("all", "common", "only_a", "only_b"):
            label = {"all": "All", "common": "Common",
                     "only_a": "Only A", "only_b": "Only B"}[filt]
            btn = ttk.Button(filters, text=label,
                             command=lambda f=filt: self._set_filter(f))
            btn.pack(side="left", padx=2)
            self.filter_buttons[filt] = btn

        self._refresh_tab_styles()
        self._refresh_filter_styles()

    # ── Search bar ─────────────────────────────────────────────────────────

    def _build_search_bar(self):
        frame = ttk.Frame(self, padding=(12, 4))
        frame.pack(fill="x")

        ttk.Label(frame, text="Search:", style="Stat.TLabel").pack(side="left", padx=(0, 6))

        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(
            frame, textvariable=self.search_var,
            bg=BG_LIGHTER, fg=FG, insertbackground=FG,
            font=("Consolas", 10), borderwidth=1, relief="solid",
            highlightbackground=BORDER, highlightthickness=1,
        )
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.search_var.trace_add("write", self._on_search_changed)

        self.lbl_match_count = ttk.Label(frame, text="", style="Stat.TLabel")
        self.lbl_match_count.pack(side="left", padx=(0, 8))

        ttk.Button(frame, text="Clear", command=self._clear_search).pack(side="left")

    def _on_search_changed(self, *_args):
        self.search_query = self.search_var.get().strip().lower()
        self._refresh_table()

    def _clear_search(self):
        self.search_var.set("")

    # ── Treeview ──────────────────────────────────────────────────────────

    def _build_treeview(self):
        container = ttk.Frame(self, padding=(12, 4))
        container.pack(fill="both", expand=True)

        self.tree = ttk.Treeview(container, show="headings", selectmode="browse")
        vsb = ttk.Scrollbar(container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self.tree.tag_configure("common", background=BG_LIGHTER, foreground=FG)
        self.tree.tag_configure("only_a", background=RED_BG, foreground=RED)
        self.tree.tag_configure("only_b", background=GREEN_BG, foreground=GREEN)

        self.tree.bind("<<TreeviewSelect>>", self._on_select)

    # ── Detail panel ──────────────────────────────────────────────────────

    def _build_detail_panel(self):
        self.detail_frame = ttk.Frame(self, padding=(12, 4))
        self.detail_frame.pack(fill="x")

        header = ttk.Frame(self.detail_frame)
        header.pack(fill="x")
        self.lbl_detail_title = ttk.Label(header, text="Entry Detail",
                                           style="Stat.TLabel")
        self.lbl_detail_title.pack(side="left")

        self.detail_text = tk.Text(
            self.detail_frame, height=10, wrap="word",
            bg=BG_LIGHTER, fg=FG, insertbackground=FG,
            font=("Consolas", 10), borderwidth=1, relief="solid",
            highlightbackground=BORDER, highlightthickness=1,
            state="disabled",
        )
        self.detail_text.pack(fill="x", pady=(4, 0))
        self.detail_text.tag_configure("key", foreground=ACCENT)
        self.detail_text.tag_configure("string", foreground=GREEN)
        self.detail_text.tag_configure("number", foreground=YELLOW)
        self.detail_text.tag_configure("hash_line", foreground=FG_DIM)
        self.detail_text.tag_configure("origin_a", foreground=RED)
        self.detail_text.tag_configure("origin_b", foreground=GREEN)
        self.detail_text.tag_configure("origin_common", foreground=FG_DIM)

    # ── Bottom bar ────────────────────────────────────────────────────────

    def _build_bottom_bar(self):
        frame = ttk.Frame(self, padding=(12, 8))
        frame.pack(fill="x")
        ttk.Button(frame, text="Apply Merge && Save",
                    style="Apply.TButton",
                    command=self._save_merged).pack(side="right")
        ttk.Button(frame, text="Export Diff Report",
                    command=self._export_report).pack(side="right", padx=(0, 8))

    # ── File loading ──────────────────────────────────────────────────────

    def _pick_file_a(self):
        p = filedialog.askopenfilename(
            title="Select File A (.sprv)",
            filetypes=[("SPRV files", "*.sprv"), ("All", "*.*")],
            initialdir=str(SCRIPT_DIR))
        if p:
            self.path_a = Path(p)
            self.lbl_path_a.config(text=f"File A: {self.path_a}")
            self._reload()

    def _pick_file_b(self):
        p = filedialog.askopenfilename(
            title="Select File B (.sprv)",
            filetypes=[("SPRV files", "*.sprv"), ("All", "*.*")],
            initialdir=str(SCRIPT_DIR))
        if p:
            self.path_b = Path(p)
            self.lbl_path_b.config(text=f"File B: {self.path_b}")
            self._reload()

    def _try_autoload(self):
        if DEFAULT_A.exists() and DEFAULT_B.exists():
            self.path_a = DEFAULT_A
            self.path_b = DEFAULT_B
            self._reload()

    def _reload(self):
        if not self.path_a or not self.path_b:
            return
        try:
            self.data_a = load_sprv(self.path_a)
            self.data_b = load_sprv(self.path_b)
        except Exception as exc:
            messagebox.showerror("Load Error", str(exc))
            return

        self.roles_diff = compute_diff(
            self.data_a.get("roles", []),
            self.data_b.get("roles", []),
        )
        self.bans_diff = compute_diff(
            self.data_a.get("bans", []),
            self.data_b.get("bans", []),
        )

        self.lbl_path_a.config(text=f"File A: {self.path_a}")
        self.lbl_path_b.config(text=f"File B: {self.path_b}")
        self._refresh_stats()
        self._refresh_table()

    # ── Stats ─────────────────────────────────────────────────────────────

    def _refresh_stats(self):
        if self.roles_diff:
            rd = self.roles_diff
            self.lbl_roles_stats.config(
                text=f"Roles:  {len(rd.common)} common  ·  "
                     f"{len(rd.only_a)} only-A  ·  {len(rd.only_b)} only-B  ·  "
                     f"{len(rd.common) + len(rd.only_a) + len(rd.only_b)} total")
        if self.bans_diff:
            bd = self.bans_diff
            self.lbl_bans_stats.config(
                text=f"Bans:   {len(bd.common)} common  ·  "
                     f"{len(bd.only_a)} only-A  ·  {len(bd.only_b)} only-B  ·  "
                     f"{len(bd.common) + len(bd.only_a) + len(bd.only_b)} total")

    # ── Section / filter switching ────────────────────────────────────────

    def _set_section(self, section: str):
        self.active_section = section
        self.sort_col = None
        self.sort_reverse = False
        self._refresh_tab_styles()
        self._refresh_table()

    def _set_filter(self, filt: str):
        self.active_filter = filt
        self._refresh_filter_styles()
        self._refresh_table()

    def _refresh_tab_styles(self):
        self.btn_roles.configure(
            style="TabActive.TButton" if self.active_section == "roles" else "Tab.TButton")
        self.btn_bans.configure(
            style="TabActive.TButton" if self.active_section == "bans" else "Tab.TButton")

    def _refresh_filter_styles(self):
        for key, btn in self.filter_buttons.items():
            btn.configure(
                style="Active.TButton" if key == self.active_filter else "TButton")

    # ── Treeview population ───────────────────────────────────────────────

    def _refresh_table(self):
        self.tree.delete(*self.tree.get_children())

        diff = self.roles_diff if self.active_section == "roles" else self.bans_diff
        if diff is None:
            return

        if self.active_section == "roles":
            cols = ("status", "platform_id", "role", "hash")
            headings = {"status": "Status", "platform_id": "Platform ID",
                        "role": "Role", "hash": "SHA-256 (short)"}
            widths = {"status": 90, "platform_id": 200, "role": 120, "hash": 220}
        else:
            cols = ("status", "banned_id", "moderator", "unban_time",
                    "times_banned", "ban_type", "hash")
            headings = {"status": "Status", "banned_id": "Banned ID",
                        "moderator": "Moderator ID", "unban_time": "Unban Time",
                        "times_banned": "# Banned", "ban_type": "Last Ban Type",
                        "hash": "SHA-256 (short)"}
            widths = {"status": 80, "banned_id": 180, "moderator": 180,
                      "unban_time": 170, "times_banned": 80,
                      "ban_type": 100, "hash": 190}

        self.tree.configure(columns=cols)
        for c in cols:
            sort_indicator = ""
            if self.sort_col == c:
                sort_indicator = " ▼" if self.sort_reverse else " ▲"
            self.tree.heading(c, text=headings[c] + sort_indicator,
                              command=lambda col=c: self._on_heading_click(col))
            self.tree.column(c, width=widths[c], minwidth=60)

        hashes_to_show = self._filtered_hashes(diff)
        all_entries: dict[str, dict] = {**diff.hash_a, **diff.hash_b}

        rows: list[tuple[str, tuple, str]] = []
        for h in hashes_to_show:
            entry = all_entries[h]
            tag = self._category_tag(h, diff)
            status_label = {"common": "Common", "only_a": "Only A",
                            "only_b": "Only B"}[tag]
            short_hash = h[:16] + "…"

            if self.active_section == "roles":
                vals = (status_label,
                        str(entry.get("platform id", "")),
                        entry.get("role", ""),
                        short_hash)
            else:
                vals = (status_label,
                        str(entry.get("banned id", "")),
                        str(entry.get("last moderator id", "")),
                        str(entry.get("unban time point", "")),
                        str(entry.get("times banned", "")),
                        entry.get("ban type", ""),
                        short_hash)

            if self.search_query:
                haystack = " ".join(str(v) for v in vals).lower() + " " + h.lower()
                if self.search_query not in haystack:
                    continue

            rows.append((h, vals, tag))

        if self.sort_col and self.sort_col in cols:
            col_idx = cols.index(self.sort_col)
            rows.sort(key=lambda r: self._sort_key(r[1][col_idx]),
                      reverse=self.sort_reverse)
        else:
            rows.sort(key=lambda r: r[0])

        for h, vals, tag in rows:
            self.tree.insert("", "end", iid=h, values=vals, tags=(tag,))

        total_before_search = len(self._filtered_hashes(diff))
        if self.search_query:
            self.lbl_match_count.config(
                text=f"{len(rows)} / {total_before_search} matches")
        else:
            self.lbl_match_count.config(text=f"{len(rows)} entries")

    @staticmethod
    def _sort_key(value: str):
        """Return a numeric key when possible so IDs sort numerically."""
        try:
            return (0, int(value))
        except (ValueError, TypeError):
            return (1, str(value).lower())

    def _on_heading_click(self, col: str):
        if self.sort_col == col:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_col = col
            self.sort_reverse = False
        self._refresh_table()

    def _filtered_hashes(self, diff: SectionDiff) -> set[str]:
        if self.active_filter == "all":
            return diff.common | diff.only_a | diff.only_b
        if self.active_filter == "common":
            return diff.common
        if self.active_filter == "only_a":
            return diff.only_a
        return diff.only_b

    @staticmethod
    def _category_tag(h: str, diff: SectionDiff) -> str:
        if h in diff.common:
            return "common"
        if h in diff.only_a:
            return "only_a"
        return "only_b"

    # ── Detail panel ──────────────────────────────────────────────────────

    def _on_select(self, _event):
        sel = self.tree.selection()
        if not sel:
            return
        h = sel[0]
        diff = self.roles_diff if self.active_section == "roles" else self.bans_diff
        if diff is None:
            return

        entry = diff.hash_a.get(h) or diff.hash_b.get(h)
        if entry is None:
            return

        tag = self._category_tag(h, diff)
        origin_map = {
            "common": ("Common to both files", "origin_common"),
            "only_a": ("Only in File A", "origin_a"),
            "only_b": ("Only in File B", "origin_b"),
        }
        origin_text, origin_tag = origin_map[tag]

        self.detail_text.configure(state="normal")
        self.detail_text.delete("1.0", "end")

        self.detail_text.insert("end", f"Origin: ")
        self.detail_text.insert("end", origin_text + "\n", origin_tag)
        self.detail_text.insert("end", f"SHA-256: ", "key")
        self.detail_text.insert("end", h + "\n\n", "hash_line")

        self._insert_json(entry)

        self.detail_text.configure(state="disabled")
        self.lbl_detail_title.config(text=f"Entry Detail  —  {origin_text}")

    def _insert_json(self, obj: dict):
        """Syntax-highlighted JSON insert into the detail text widget."""
        lines = json.dumps(obj, indent=4).splitlines()
        for line in lines:
            stripped = line.lstrip()
            indent = line[: len(line) - len(stripped)]
            self.detail_text.insert("end", indent)

            if stripped.startswith('"') and '": ' in stripped:
                key_end = stripped.index('": ') + 1
                self.detail_text.insert("end", stripped[:key_end], "key")
                rest = stripped[key_end:]
                self._insert_value(rest)
            elif stripped.startswith('"'):
                self.detail_text.insert("end", stripped, "string")
            else:
                self._insert_value(stripped)
            self.detail_text.insert("end", "\n")

    def _insert_value(self, text: str):
        t = text.strip().rstrip(",")
        if t.startswith('"'):
            self.detail_text.insert("end", text, "string")
        elif t in ("{", "}", "[", "]", ""):
            self.detail_text.insert("end", text)
        else:
            self.detail_text.insert("end", text, "number")

    # ── Save / export ─────────────────────────────────────────────────────

    def _save_merged(self):
        if not self.roles_diff or not self.bans_diff:
            messagebox.showwarning("No data", "Load both files first.")
            return

        path = filedialog.asksaveasfilename(
            title="Save merged SPRV",
            defaultextension=".sprv",
            filetypes=[("SPRV files", "*.sprv"), ("All", "*.*")],
            initialfile=DEFAULT_OUT.name,
            initialdir=str(SCRIPT_DIR))
        if not path:
            return

        merged_roles = self._merged_entries(self.roles_diff)
        merged_bans = self._merged_entries(self.bans_diff)

        merged = {
            "bbmeta": (self.data_a or {}).get(
                "bbmeta", (self.data_b or {}).get("bbmeta", "")),
            "roles": merged_roles,
            "bans": merged_bans,
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(merged, f, indent=4)

        messagebox.showinfo(
            "Saved",
            f"Merged file written.\n\n"
            f"Roles: {len(merged_roles)}   Bans: {len(merged_bans)}\n"
            f"Path: {path}")

    @staticmethod
    def _merged_entries(diff: SectionDiff) -> list[dict]:
        all_hashes = diff.common | diff.only_a | diff.only_b
        merged: dict[str, dict] = {**diff.hash_a, **diff.hash_b}
        return [merged[h] for h in sorted(all_hashes)]

    def _export_report(self):
        if not self.roles_diff or not self.bans_diff:
            messagebox.showwarning("No data", "Load both files first.")
            return

        path = filedialog.asksaveasfilename(
            title="Export diff report",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All", "*.*")],
            initialfile="sprv_diff_report.txt",
            initialdir=str(SCRIPT_DIR))
        if not path:
            return

        lines: list[str] = []
        for name, diff in [("ROLES", self.roles_diff), ("BANS", self.bans_diff)]:
            lines.append(f"{'=' * 60}")
            lines.append(f"  {name}")
            lines.append(f"{'=' * 60}")
            lines.append(f"  Common: {len(diff.common)}")
            lines.append(f"  Only A: {len(diff.only_a)}")
            lines.append(f"  Only B: {len(diff.only_b)}")
            lines.append("")

            if diff.only_a:
                lines.append(f"  --- Entries only in File A ---")
                for h in sorted(diff.only_a):
                    lines.append(f"  [{h[:16]}]  "
                                 f"{json.dumps(diff.hash_a[h], separators=(',', ': '))}")
                lines.append("")

            if diff.only_b:
                lines.append(f"  +++ Entries only in File B +++")
                for h in sorted(diff.only_b):
                    lines.append(f"  [{h[:16]}]  "
                                 f"{json.dumps(diff.hash_b[h], separators=(',', ': '))}")
                lines.append("")

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        messagebox.showinfo("Exported", f"Diff report saved to:\n{path}")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = MergeTool()
    app.mainloop()
