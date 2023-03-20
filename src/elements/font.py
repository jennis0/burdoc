from dataclasses import dataclass

@dataclass
class Font:
    name: str
    family: str
    size: float
    colour: int
    bold: bool
    italic: bool
    superscript: bool

    def __repr__(self):
        return f"<Font {self.name} Family={self.family} Size={self.size} Colour={self.colour} b={self.bold} i={self.italic} s={self.superscript}>"

    def to_json(self):
        return {'type':'font', 'font':self.name, 'family':self.family, 'size':self.size, 'colour':self.colour, 'bold':self.bold, 'italic':self.italic, 'superscript':self.superscript}
