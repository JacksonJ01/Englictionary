import pandas as pd

from config import DEFINITION_COLUMN, FOCUS_COLUMN, POS_COLUMN


STANDARD_COLUMNS = ("Word", "POS", "Definition")


def _case_insensitive_lookup(columns):
    return {str(column).strip().lower(): column for column in columns}


def _resolve_column(df, requested_name, fallback_candidates=()):
    lookup = _case_insensitive_lookup(df.columns)
    if requested_name:
        match = lookup.get(str(requested_name).strip().lower())
        if match is not None:
            return match

    for candidate in fallback_candidates:
        match = lookup.get(str(candidate).strip().lower())
        if match is not None:
            return match

    return None


def _prompt_for_column(df, label, default_name=None):
    columns = list(df.columns)
    print(f"Select {label} column:")
    for index, column in enumerate(columns, start=1):
        suffix = ""
        if default_name and str(column).strip().lower() == str(default_name).strip().lower():
            suffix = " (default)"
        print(f"  {index}. {column}{suffix}")

    while True:
        choice = input(
            f"Enter the number for the {label} column{(' [default ' + str(default_name) + ']') if default_name else ''}: "
        ).strip()
        if not choice and default_name:
            match = _resolve_column(df, default_name)
            if match is not None:
                return match

        if choice.isdigit():
            selected_index = int(choice)
            if 1 <= selected_index <= len(columns):
                return columns[selected_index - 1]

        print("Please enter a valid number from the list.")


def _normalize_text(series):
    return series.fillna("").astype(str).str.strip()


def load_data(file_path, focus_column=None, definition_column=None, pos_column=None):
    df = pd.read_csv(file_path)

    focus_source = _resolve_column(
        df,
        focus_column or FOCUS_COLUMN,
        fallback_candidates=("Word", "term", "study_term", "title", "name"),
    )
    definition_source = _resolve_column(
        df,
        definition_column or DEFINITION_COLUMN,
        fallback_candidates=("Definition", "definition", "meaning", "explanation", "description"),
    )
    pos_source = _resolve_column(
        df,
        pos_column or POS_COLUMN,
        fallback_candidates=("POS", "pos", "part_of_speech", "category", "type"),
    )

    if focus_source is None:
        focus_source = _prompt_for_column(df, "focused", default_name=FOCUS_COLUMN)

    if definition_source is None:
        definition_source = _prompt_for_column(df, "definition", default_name=DEFINITION_COLUMN)

    normalized = pd.DataFrame(index=df.index)
    normalized["Word"] = _normalize_text(df[focus_source])
    normalized["Definition"] = _normalize_text(df[definition_source])
    normalized["POS"] = _normalize_text(df[pos_source]) if pos_source is not None else ""

    excluded_columns = {
        str(column).strip().lower()
        for column in (focus_source, definition_source, pos_source, *STANDARD_COLUMNS)
        if column is not None
    }
    detail_columns = [column for column in df.columns if str(column).strip().lower() not in excluded_columns]

    for column in detail_columns:
        normalized[column] = df[column]

    normalized.attrs["source_file"] = str(file_path)
    normalized.attrs["focus_column"] = str(focus_source)
    normalized.attrs["definition_column"] = str(definition_source)
    normalized.attrs["pos_column"] = str(pos_source) if pos_source is not None else ""
    normalized.attrs["detail_columns"] = tuple(detail_columns)
    normalized.attrs["source_columns"] = tuple(df.columns)

    ordered_columns = [*STANDARD_COLUMNS, *detail_columns]
    return normalized.loc[:, ordered_columns].copy()
