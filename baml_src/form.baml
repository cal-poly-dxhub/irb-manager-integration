class Paragraph {
  type string
  id string
  content string
  page int
}

class Table {
  type string
  id string
  content string[][]
  page int
}

class ParsedContent {
  elements (Paragraph | Table)[]
}

class ParagraphField {
  id string
  title string
  type string // "paragraph"
  content string
  page int
  instructions string?
}

class TableField {
  id string
  title string
  type string // "table"
  content string[][]
  headers string[]
  page int
  instructions string?
}

class GroupedField {
  id string
  title string
  section_number string?
  type string // "grouped"
  content FormMember[]
  page int
  instructions string?
}

class FormMember {
  field (ParagraphField | TableField | GroupedField)
}

class Form {
  members FormMember[]
}
