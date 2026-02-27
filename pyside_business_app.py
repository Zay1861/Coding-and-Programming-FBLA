#!/usr/bin/env python3
"""Small PySide6 prototype that lists businesses from coding_programming_data.json
Save this file next to your existing Python script and run:

    python3 ./pyside_business_app.py

Install dependency:
    python3 -m pip install PySide6
"""
import json
import os
import sys
from PySide6 import QtWidgets, QtGui, QtCore

DATA_FILE = os.path.join(os.path.dirname(__file__), "coding_programming_data.json")


def load_data():
    if not os.path.exists(DATA_FILE):
        return {"businesses": []}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"businesses": []}


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Business Review - PySide6 Prototype")
        self.resize(900, 520)

        self.table = QtWidgets.QTableView()
        self.setCentralWidget(self.table)

        self.model = QtGui.QStandardItemModel()
        headers = ["ID", "Business Name", "Category", "Address", "Deal", "Rating"]
        self.model.setHorizontalHeaderLabels(headers)
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)

        toolbar = self.addToolBar("main")
        reload_act = QtGui.QAction("Reload", self)
        reload_act.triggered.connect(self.load_and_populate)
        toolbar.addAction(reload_act)

        self.load_and_populate()

    def load_and_populate(self):
        self.model.removeRows(0, self.model.rowCount())
        data = load_data()
        businesses = data.get("businesses", [])
        for b in businesses:
            biz_id = b.get("id", "")
            name = b.get("name", "")
            cat = b.get("category", "")
            addr = b.get("address", "")
            deal = b.get("deal", "")
            reviews = b.get("reviews", [])
            avg = 0.0
            if reviews:
                try:
                    avg = round(sum((r.get("rating", 0) for r in reviews)) / len(reviews), 1)
                except Exception:
                    avg = 0.0
            rating_text = f"{avg} ({len(reviews)} reviews)"

            row = [
                QtGui.QStandardItem(str(biz_id)),
                QtGui.QStandardItem(name),
                QtGui.QStandardItem(cat),
                QtGui.QStandardItem(addr),
                QtGui.QStandardItem(deal),
                QtGui.QStandardItem(rating_text),
            ]
            for item in row:
                item.setEditable(False)
            self.model.appendRow(row)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
