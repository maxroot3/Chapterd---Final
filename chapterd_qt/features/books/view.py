"""The book screen: two tabs, Book Log (add / search / remove buttons + filters) and Reading Summary."""
from html import escape

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
    QTabWidget, QVBoxLayout, QWidget,
)

from features.books.service import STATUSES, BookError
from features.books.widgets import BookForm, BookTable, stars


class BookDialog(QDialog):
    """Pop-up form used for both Add Book and editing an existing book (double-click a row)."""

    def __init__(self, parent, title, button_text, save, book=None):
        super().__init__(parent)
        self.save = save  # function(values) that raises BookError if the book is invalid
        self.setWindowTitle(title)
        self.setMinimumWidth(460)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(14)
        self.form = BookForm()
        if book:
            self.form.set_book(book)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        confirm = QPushButton(button_text)
        confirm.setObjectName("primaryButton")
        confirm.setDefault(True)
        confirm.clicked.connect(self.submit)
        buttons.addWidget(cancel)
        buttons.addWidget(confirm)
        layout.addWidget(self.form)
        layout.addLayout(buttons)

    def submit(self):
        try:
            self.save(self.form.values())
        except BookError as error:
            QMessageBox.warning(self, "Chapterd", str(error))
            return  # stay open so the user can fix the problem
        self.accept()


class BookView(QWidget):
    """Two tabs: Book Log and Reading Summary."""

    def __init__(self, books):
        super().__init__()
        self.books = books

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        self.tabs.addTab(self._log_tab(), "Book Log")
        self.tabs.addTab(self._stats_tab(), "Reading Summary")
        for index in range(self.tabs.count()):
            self.tabs.widget(index).layout().setContentsMargins(20, 22, 20, 20)
        self.tabs.currentChanged.connect(lambda _: self.refresh())
        self.reset()

    # ----- tabs -----
    def _log_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        # buttons: Add Book, Search Book, Remove Book
        buttons = QHBoxLayout()
        add_button = QPushButton("Add Book")
        add_button.setObjectName("primaryButton")
        add_button.clicked.connect(self.add_book)
        self.edit_button = QPushButton("Edit Book")
        self.edit_button.setEnabled(False)  # needs a selected book
        self.edit_button.clicked.connect(self.edit_book)
        self.search_button = QPushButton("Search Book")
        self.search_button.setCheckable(True)  # click once to show the search box, again to hide it
        self.search_button.toggled.connect(self.toggle_search)
        self.remove_button = QPushButton("Remove Book")
        self.remove_button.setObjectName("dangerButton")
        self.remove_button.setEnabled(False)
        self.remove_button.clicked.connect(self.remove_book)
        buttons.addWidget(add_button)
        buttons.addWidget(self.edit_button)
        buttons.addWidget(self.search_button)
        buttons.addWidget(self.remove_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        # search box (hidden until Search Book is clicked)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search title, author, or genre...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self.refresh_log)
        self.search_input.setVisible(False)
        layout.addWidget(self.search_input)

        # filters: Status and Rating dropdowns
        filters = QHBoxLayout()
        self.status_filter = QComboBox()
        self.status_filter.addItem("All Statuses", None)
        for status in STATUSES:
            self.status_filter.addItem(status, status)
        self.rating_filter = QComboBox()
        self.rating_filter.addItem("All Ratings", None)
        for rating in range(5, 0, -1):
            self.rating_filter.addItem(stars(rating), rating)
        self.rating_filter.addItem(stars(0), 0)  # "Unrated"
        for combo in (self.status_filter, self.rating_filter):
            combo.setMinimumWidth(150)
            combo.currentIndexChanged.connect(self.refresh_log)
        filters.addWidget(QLabel("Filter by:"))
        filters.addWidget(self.status_filter)
        filters.addWidget(self.rating_filter)
        filters.addStretch(1)
        layout.addLayout(filters)

        self.log_table = BookTable()
        self.log_table.itemSelectionChanged.connect(self.update_buttons)
        self.log_table.itemDoubleClicked.connect(lambda _: self.edit_book())
        layout.addWidget(self.log_table, 1)

        hint = QLabel("Select a book, then use Edit Book or Remove Book (double-click also edits).")
        hint.setObjectName("appSubtitle")
        layout.addWidget(hint)
        return page

    def _stats_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        self.stats_label = QLabel()
        self.stats_label.setObjectName("statsText")
        self.stats_label.setTextFormat(Qt.TextFormat.RichText)
        self.stats_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.stats_label)
        return page

    # ----- refresh -----
    def reset(self):
        """Opens the log clean: no search, no filters, nothing selected."""
        self.search_button.setChecked(False)  # hides and clears the search box
        self.search_input.clear()
        self.status_filter.setCurrentIndex(0)
        self.rating_filter.setCurrentIndex(0)
        self.tabs.setCurrentIndex(0)
        self.refresh()

    def update_buttons(self):
        selected = self.log_table.selected_book() is not None
        self.edit_button.setEnabled(selected)
        self.remove_button.setEnabled(selected)

    def refresh(self):
        self.refresh_log()
        self.refresh_stats()

    def refresh_log(self):
        """Reloads the table using the search text and the Status / Rating filters."""
        books = self.books.search_books(self.search_input.text())
        status = self.status_filter.currentData()
        rating = self.rating_filter.currentData()
        if status is not None:
            books = [b for b in books if b["status"] == status]
        if rating is not None:
            books = [b for b in books if b["rating"] == rating]
        self.log_table.load(books)
        self.update_buttons()

    def refresh_stats(self):
        s = self.books.summary_stats()
        # escape() stops characters like < and & in book data from breaking the HTML below
        rows = "".join(
            f"<tr><td>{escape(k)}</td><td><b>{v}</b></td></tr>" for k, v in s["by_status"].items()
        )
        avg = s["average_rating"] if s["average_rating"] is not None else "n/a"
        if s["top_author"]:
            author, count = s["top_author"]
            top = f"{escape(author)} ({count} {'book' if count == 1 else 'books'})"  # 1 book / 2 books
        else:
            top = "n/a"
        self.stats_label.setText(
            f"<h2>Reading Summary</h2>"
            f"<p>Total books: <b>{s['total']}</b></p>"
            f"<table cellspacing='6'>{rows}</table>"
            f"<p>Average rating: <b>{avg}</b></p>"
            f"<p>Most-logged author: <b>{top}</b></p>"
        )

    # ----- actions -----
    def toggle_search(self, checked):
        self.search_input.setVisible(checked)
        if checked:
            self.search_input.setFocus()
        else:
            self.search_input.clear()  # hiding the box also clears the search

    def add_book(self):
        dialog = BookDialog(self, "Add Book", "Add Book", lambda values: self.books.add_book(*values))
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()
            QMessageBox.information(self, "Chapterd", "Book added!")

    def edit_book(self):
        book = self.log_table.selected_book()
        if not book:
            return
        dialog = BookDialog(
            self, "Edit Book", "Save Changes",
            lambda values: self.books.update_book(book["id"], *values), book,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()
            QMessageBox.information(self, "Chapterd", "Changes saved!")

    def remove_book(self):
        book = self.log_table.selected_book()
        if not book:
            return
        answer = QMessageBox.question(
            self, "Remove Book", f'Remove "{book["title"]}" from your log?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            try:
                self.books.remove_book(book["id"])
            except BookError as error:
                QMessageBox.warning(self, "Chapterd", str(error))
                return
            self.refresh()
