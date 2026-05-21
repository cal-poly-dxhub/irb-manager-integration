client<llm> ClaudeSonnetBedrock {
  provider aws-bedrock
  options {
    model "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
    region "us-west-2"
  }
}

function RefineForm(parsed_content: ParsedContent) -> Form {
  client ClaudeSonnetBedrock

  prompt #"
    You are an expert at analyzing research compliance forms. You will receive
    an unstructured form that contains a mix of paragraphs and tables extracted
    from a scanned document

    Your task is to reorganize this content into a structured set of fields,
    where each field represents a distinct question or data point on the form.
    Note that there can be multiple fields per input element or one field spread
    across multiple input elements.

    Guidelines:
    1. Identify the main question or prompt for each field
    2. For each field, provide both:
       - id: A unique, descriptive programmatic identifier (e.g., "principal_investigator",
         "study_title", "funding_source") - use snake_case, lowercase
       - title: The actual human-readable field name or label as it appears in the form
         (e.g., "Principal Investigator", "Study Title", "Funding Source")
    3. Preserve the content type - keep paragraphs as paragraphs and tables as tables
       - For paragraph fields, set type="paragraph"
       - For table fields, set type="table" and extract headers from the first row
       - For grouped sections, set type="grouped" and include related fields in content
    4. Group related content together into single fields when appropriate
    5. Maintain the logical order from the original form
    6. Clean up OCR artifacts and fix obvious formatting issues
    7. For the instructions field: Only populate this if the field has explicit,
       visible instructions (e.g., "Please provide...", "Enter all...", "List below...").
       Leave it empty/null if there are no explicit instructions for that field

    Input Form (raw paragraphs and tables):
    {{ parsed_content }}

    Please restructure this into fields with clear questions and organized content.

    {{ ctx.output_format }}
  "#
}
