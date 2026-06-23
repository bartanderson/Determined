from __future__ import annotations

from typing import Any, Dict, List


def _render_function(function: Dict[str, Any]) -> str:
    arguments = ", ".join(function["arguments"])

    return (
        f"- FUNCTION {function['name']}("
        f"{arguments}) "
        f"[line {function['line_number']}] "
        f"-> {function['return_type']}"
    )


def _render_class(class_info: Dict[str, Any]) -> str:
    base_classes = ", ".join(class_info["base_classes"])

    if not base_classes:
        base_classes = "None"

    methods = ", ".join(class_info["methods"])

    return (
        f"- CLASS {class_info['name']} "
        f"[line {class_info['line_number']}] "
        f"bases=[{base_classes}] "
        f"methods=[{methods}]"
    )


def _render_import(import_info: Dict[str, Any]) -> str:
    return (
        f"- IMPORT {import_info['module']} "
        f"({import_info['import_type']}) "
        f"[line {import_info['line_number']}]"
    )


def _render_mutation(mutation: Dict[str, Any]) -> str:
    return (
        f"- MUTATION "
        f"target={mutation['target']} "
        f"operation={mutation['operation']} "
        f"[line {mutation['line_number']}]"
    )


def _render_contract(contract: Dict[str, Any]) -> str:
    side_effects = ", ".join(contract["side_effects"])
    behaviors = ", ".join(contract["testable_behaviors"])

    return (
        f"- CONTRACT {contract['function_name']} "
        f"[line {contract['line_number']}] "
        f"complexity={contract['complexity_score']} "
        f"description='{contract['description']}' "
        f"side_effects=[{side_effects}] "
        f"behaviors=[{behaviors}]"
    )


def render_file_analysis_for_llm(
    file_analysis: Dict[str, Any],
) -> str:
    lines: List[str] = []

    file_info = file_analysis["file"]

    lines.append(
        f"FILE: {file_info['file_path']}"
    )

    lines.append(
        f"ROLE: {file_info['role']}"
    )

    lines.append(
        f"LINES: {file_info['line_count']}"
    )

    lines.append(
        f"HOT: {file_info['is_hot']}"
    )

    lines.append("")

    if file_analysis["imports"]:
        lines.append("IMPORTS:")

        for import_info in file_analysis["imports"]:
            lines.append(
                _render_import(import_info)
            )

        lines.append("")

    if file_analysis["classes"]:
        lines.append("CLASSES:")

        for class_info in file_analysis["classes"]:
            lines.append(
                _render_class(class_info)
            )

        lines.append("")

    if file_analysis["functions"]:
        lines.append("FUNCTIONS:")

        for function in file_analysis["functions"]:
            lines.append(
                _render_function(function)
            )

        lines.append("")

    if file_analysis["mutations"]:
        lines.append("MUTATIONS:")

        for mutation in file_analysis["mutations"]:
            lines.append(
                _render_mutation(mutation)
            )

        lines.append("")

    if file_analysis["behavioral_contracts"]:
        lines.append("BEHAVIORAL CONTRACTS:")

        for contract in file_analysis["behavioral_contracts"]:
            lines.append(
                _render_contract(contract)
            )

        lines.append("")

    return "\n".join(lines)


def render_context_bundle_for_llm(
    context_bundle: Dict[str, Any],
) -> str:
    output_sections: List[str] = []

    entry_file = context_bundle.get("entry_file")

    if entry_file is not None:
        output_sections.append("=== ENTRY FILE ===")
        output_sections.append(
            render_file_analysis_for_llm(entry_file)
        )

    related_files = context_bundle.get("related_files", [])

    if related_files:
        output_sections.append("=== RELATED FILES ===")

        entry_path = entry_file.get("file_path") if entry_file else None
        seen_paths = set()

        # mark entry file so it never repeats in related section
        if entry_path:
            seen_paths.add(entry_path)

        for related_file in related_files:
            file_path = related_file.get("file_path")

            # skip duplicates across entry + related + internal repeats
            if file_path in seen_paths:
                continue

            seen_paths.add(file_path)

            output_sections.append(
                render_file_analysis_for_llm(related_file)
            )

    return "\n\n".join(output_sections)