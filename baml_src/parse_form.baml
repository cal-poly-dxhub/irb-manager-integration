client<llm> Claude {
  provider anthropic
  options {
    model "claude-3-5-sonnet-latest"
  }
}

function ParseForm(document: string) -> Form {
  client Claude

  prompt #"
    You are a document processing assistant. You will receive the contents
    of a scanned form represented as a sequence of paragraphs and tables.

    Your task is to parse the form into structured sections and fields.

    Rules:
    - Each Section has a title and a list of fields.
    - A Field has a page number, a type, a label (the instruction or
      question), and a value (the response or filled-in content).
    - When several fields logically belong together (e.g. address parts,
      name components, or a set of checkboxes under one heading), group
      them into a GroupedField with a shared label.
    - Use the most specific FieldType for each field:
      TEXT for free-text, NUMBER for numeric, DATE for dates,
      BOOLEAN for yes/no or checkboxes, SELECTION for single-choice,
      MULTI_SELECTION for multi-choice, SIGNATURE for signatures,
      TEXTAREA for long-form text.
    - Preserve the order of appearance in the document.
    - If a field is blank or not filled in, set value to an empty string.
    - Clean up OCR artifacts, fix obvious typos, and separate content
      that was accidentally joined during text extraction.

    Document:
    ---
    {{ document }}
    ---

    {{ ctx.output_format }}
  "#
}
