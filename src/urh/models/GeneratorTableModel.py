from PyQt5.QtCore import Qt, QModelIndex
from PyQt5.QtGui import QColor, QFont

from urh import constants
from urh.models.ProtocolTreeItem import ProtocolTreeItem
from urh.models.TableModel import TableModel
from urh.signalprocessing.ProtocolAnalyzerContainer import ProtocolAnalyzerContainer
from urh.ui.actions.Clear import Clear
from urh.ui.actions.DeleteBitsAndPauses import DeleteBitsAndPauses
from urh.ui.actions.InsertBitsAndPauses import InsertBitsAndPauses
from urh.ui.actions.InsertColumn import InsertColumn
from urh.util.Logger import logger


class GeneratorTableModel(TableModel):
    def __init__(self, tree_root_item: ProtocolTreeItem, modulators, parent = None):
        super().__init__(parent)
        self.protocol = ProtocolAnalyzerContainer(modulators)
        self.tree_root_item = tree_root_item
        self.dropped_row = -1

        self.cfc = None
        self.is_writeable = True
        self.decode = False
        self.is_generator = True

    def refresh_fonts(self):
        self.bold_fonts.clear()
        self.text_colors.clear()
        pac = self.protocol
        for i, block in enumerate(pac.blocks):
            if block.fuzz_created:
                for lbl in (lbl for lbl in block.labelset if lbl.fuzz_created):
                    for j in range(*block.get_label_range(lbl=lbl, view=self.proto_view, decode=False)):
                        self.bold_fonts[i, j] = True

            for lbl in block.active_fuzzing_labels:
                for j in range(*block.get_label_range(lbl=lbl, view=self.proto_view, decode=False)):
                    self.bold_fonts[i, j] = True
                    self.text_colors[i, j] = QColor("orange")

    def delete_range(self, block_start: int, block_end: int, index_start: int, index_end: int):
        if block_start > block_end:
            block_start, block_end = block_end, block_start
        if index_start > index_end:
            index_start, index_end = index_end, index_start

        remove_action = DeleteBitsAndPauses(self.protocol, block_start, block_end, index_start,
                                            index_end, self.proto_view, False)
        ########## Zugehörige Pausen löschen
        self.undo_stack.push(remove_action)

    def flags(self, index: QModelIndex):
        if not index.isValid():
            return Qt.ItemIsEnabled

        return Qt.ItemIsEnabled | Qt.ItemIsDropEnabled | Qt.ItemIsSelectable | Qt.ItemIsDragEnabled | Qt.ItemIsEditable

    def supportedDropActions(self):
        return Qt.CopyAction | Qt.MoveAction

    def dropMimeData(self, mimedata, action, row, column, parentIndex):
        if action == Qt.IgnoreAction:
            return True

        data_str = str(mimedata.text())
        indexes = list(data_str.split("/")[:-1])

        group_nodes = []
        file_nodes = []
        for index in indexes:
            row, column, parent = map(int, index.split(","))
            if parent == -1:
                parent = self.tree_root_item
            else:
                parent = self.tree_root_item.child(parent)
            node = parent.child(row)
            if node.is_group:
                group_nodes.append(node)
            else:
                file_nodes.append(node)

        # Which Nodes to add?
        nodes_to_add = []
        """:type: list of ProtocolTreeItem """
        for group_node in group_nodes:
            nodes_to_add.extend(group_node.children)
        nodes_to_add.extend([file_node for file_node in file_nodes if file_node not in nodes_to_add])

        for node in reversed(nodes_to_add):
            undo_action = InsertBitsAndPauses(self.protocol, self.dropped_row, node.protocol)
            self.undo_stack.push(undo_action)

        return True

    def clear(self):
        clear_action = Clear(self.protocol)
        self.undo_stack.push(clear_action)

    def duplicate_row(self, row: int):
        self.protocol.duplicate_line(row)
        self.update()

    def get_selected_label_index(self, row: int, column: int):
        try:
            block = self.protocol.blocks[row]
        except IndexError:
            logger.warning("{} is out of range for generator protocol".format(row))
            return -1

        for i, lbl in enumerate(block.labelset):
            if column in range(*block.get_label_range(lbl, self.proto_view, False)):
                return i

        return -1

    def insert_column(self, index: int):
        insert_action = InsertColumn(self.protocol, index, self.proto_view)
        self.undo_stack.push(insert_action)
