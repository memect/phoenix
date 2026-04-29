"""
结构化数据类型定义

提供 Table 和 Cell 类用于处理表格数据。
"""

import numpy


class Cell:
    """表格单元格类"""
    
    def __init__(self, text: str, row_index: int, col_index: int, row_span: int, col_span: int):
        self.text = text
        self.__row_span = row_span
        self.__col_span = col_span
        self.__row_index = row_index
        self.__col_index = col_index

    def __str__(self):
        return self.text

    @property
    def row_span(self):
        return self.__row_span

    @property
    def col_span(self):
        return self.__col_span

    @property
    def row_index(self):
        return self.__row_index

    @property
    def col_index(self):
        return self.__col_index


class Table:
    """表格类"""
    
    def __init__(self, table_data: numpy.ndarray, row_num: int, col_num: int):
        self.__table_data = table_data
        self.__row_num = row_num
        self.__col_num = col_num

        _cells = []
        _cell_set = set()
        for row in table_data:
            for cell in row:
                if cell not in _cell_set:
                    _cell_set.add(cell)
                    _cells.append(cell)
        self.__cells = tuple(_cells)
    
    @property
    def row_num(self):
        return self.__row_num
    
    @property
    def col_num(self):
        return self.__col_num
    
    @property
    def table_data(self):
        return self.__table_data.copy()

    @property
    def cells(self):
        return self.__cells

    def __getitem__(self, row_slice: slice, col_slice: slice) -> Cell:
        return self.__table_data[row_slice, col_slice]

    def get_right_neighbor(self, cell: Cell) -> list[Cell]:
        ret = []
        for c in self.cells:
            if c.col_index == cell.col_index + cell.col_span \
                and set(range(c.row_index, c.row_index + c.row_span)) & set(range(cell.row_index, cell.row_index + cell.row_span)):
                ret.append(c)
        return ret

    def get_left_neighbor(self, cell: Cell) -> list[Cell]:
        ret = []
        for c in self.cells:
            if c.col_index + c.col_span == cell.col_index \
                and set(range(c.row_index, c.row_index + c.row_span)) & set(range(cell.row_index, cell.row_index + cell.row_span)):
                ret.append(c)
        return ret
    
    def get_down_neighbor(self, cell: Cell) -> list[Cell]:
        ret = []
        for c in self.cells:
            if c.row_index == cell.row_index + cell.row_span \
                and set(range(c.col_index, c.col_index + c.col_span)) & set(range(cell.col_index, cell.col_index + cell.col_span)):
                ret.append(c)
        return ret

    def get_up_neighbor(self, cell: Cell) -> list[Cell]:
        ret = []
        for c in self.cells:
            if c.row_index + c.row_span == cell.row_index \
                and set(range(c.col_index, c.col_index + c.col_span)) & set(range(cell.col_index, cell.col_index + cell.col_span)):
                ret.append(c)
        return ret
        
    def __str__(self):
        return "\n".join(["\t".join([str(cell) for cell in row]) for row in self.__table_data])
