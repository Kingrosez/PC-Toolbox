"""Table component for PC-Toolbox data display."""

import customtkinter as ctk
from tkinter import ttk
from typing import List, Dict, Any


class DataTable(ctk.CTkFrame):
    """Treeview-based data table component."""

    def __init__(self, master, columns: List[str], headings: Dict[str, str] = None,
                 show: str = "headings", height: int = 10):
        super().__init__(
            master,
            fg_color=master.theme.colors["secondary_panel"],
            corner_radius=4
        )

        self.columns = columns
        self.tree = ttk.Treeview(
            self,
            columns=columns,
            show=show,
            height=height
        )

        # Configure column headings
        if headings:
            for col in columns:
                if col in headings:
                    self.tree.heading(col, text=headings[col])
                    # Set column width based on heading
                    self.tree.column(col, width=100, minwidth=50, anchor="w")
                else:
                    self.tree.heading(col, text=col.title())
                    self.tree.column(col, width=100, minwidth=50, anchor="w")
        else:
            for col in columns:
                self.tree.heading(col, text=col.title())
                self.tree.column(col, width=100, minwidth=50, anchor="w")

        # Scrollbar
        scrollbar = ctk.CTkScrollbar(
            self,
            command=self.tree.yview
        )
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def insert_data(self, data: List[Dict[str, Any]]):
        """Insert data rows into the table."""
        for item in data:
            values = []
            for col in self.columns:
                val = item.get(col, "")
                if isinstance(val, (int, float)):
                    val = str(val)
                values.append(val)
            self.tree.insert("", "end", values=values)

    def clear_data(self):
        """Clear all data from the table."""
        for item in self.tree.get_children():
            self.tree.delete(item)

    def select_item(self, item_id):
        """Select a specific item."""
        self.tree.selection_set(item_id)

    def get_selected_items(self) -> List[str]:
        """Get IDs of selected items."""
        return self.tree.selection()

    def delete_selected(self):
        """Delete selected items."""
        for item in self.tree.selection():
            self.tree.delete(item)


class SearchableTable(DataTable):
    """Data table with search functionality."""

    def __init__(self, master, columns: List[str], headings: Dict[str, str] = None, **kwargs):
        super().__init__(master, columns, headings, **kwargs)
        self.search_var = ctk.StringVar()
        self._setup_search()

    def _setup_search(self):
        """Set up search control above the table."""
        self.search_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.search_entry = ctk.CTkEntry(
            self.search_frame,
            textvariable=self.search_var,
            placeholder_text="Search...",
            width=200,
            height=30,
            font=ctk.CTkFont(size=12),
            fg_color=self.master.theme.colors["secondary_panel"],
            border_width=1,
            border_color=self.master.theme.colors["muted_text"],
        )
        self.search_entry.pack(side="left")
        self.search_var.trace_add("write", self._on_search_change)
        self.search_frame.pack(fill="x", padx=4, pady=4)

    def _on_search_change(self, *args):
        """Filter table rows based on search text."""
        search_text = self.search_var.get().lower()
        for item in self.tree.get_children():
            values = self.tree.item(item, "values")
            match = any(search_text in str(v).lower() for v in values)
            self.tree.item(item, open=match)  # Simplified filtering