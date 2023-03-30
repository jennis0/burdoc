"""Elements are (mostly) objects that have a physical location within a PDF page.

Elements generally inherit from LayoutElement to provide a consistent interface for accessing location
information.
"""

from .aside import Aside
from .bbox import Bbox, Point
from .drawing import DrawingElement, DrawingType
from .element import LayoutElement, LayoutElementGroup
from .font import Font
from .image import ImageElement, ImageType
from .line import LineElement
from .section import PageSection
from .span import Span
from .table import Table, TableParts
from .textblock import TextBlock, TextBlockType
from .textlist import TextList, TextListItem