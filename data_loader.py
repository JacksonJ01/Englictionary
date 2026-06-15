import pandas as pd

from config import (
    DEFINITION_COLUMN,
    DEFINITION_COLUMN_CANDIDATES,
    SOURCE_COLUMN_LIMIT,
    TERM_COLUMN,
    TERM_COLUMN_CANDIDATES,
)


STANDARD_COLUMNS = ("Term", "Definition")


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


def _default_column(columns, index):
    if 0 <= index < len(columns):
        return columns[index]
    return None


def load_data(file_path, focus_column=None, definition_column=None):
    df = pd.read_csv(file_path)
    if SOURCE_COLUMN_LIMIT:
        df = df.iloc[:, :SOURCE_COLUMN_LIMIT].copy()
    columns = list(df.columns)

    focus_source = _resolve_column(
        df,
        focus_column or TERM_COLUMN,
        fallback_candidates=TERM_COLUMN_CANDIDATES,
    )
    definition_source = _resolve_column(
        df,
        definition_column or DEFINITION_COLUMN,
        fallback_candidates=DEFINITION_COLUMN_CANDIDATES,
    )

    if focus_source is None:
        focus_source = _default_column(columns, 0)

    if definition_source is None:
        definition_source = _default_column(columns, 1) or focus_source

    if focus_source is None or definition_source is None:
        raise ValueError("The source CSV must contain at least one column.")

    normalized = pd.DataFrame(index=df.index)
    normalized["Term"] = _normalize_text(df[focus_source])
    normalized["Definition"] = _normalize_text(df[definition_source])
    # Backward-compatible alias for older modules that still read Word.
    normalized["Word"] = normalized["Term"]

    excluded_columns = {
        str(column).strip().lower()
        for column in (focus_source, definition_source, *STANDARD_COLUMNS, "Word")
        if column is not None
    }
    detail_columns = [column for column in df.columns if str(column).strip().lower() not in excluded_columns]

    for column in detail_columns:
        normalized[column] = df[column]

    normalized.attrs["source_file"] = str(file_path)
    normalized.attrs["focus_column"] = str(focus_source)
    normalized.attrs["definition_column"] = str(definition_source)
    normalized.attrs["detail_columns"] = tuple(detail_columns)
    normalized.attrs["source_columns"] = tuple(df.columns)

    ordered_columns = [*STANDARD_COLUMNS, "Word", *detail_columns]
    return normalized.loc[:, ordered_columns].copy()
