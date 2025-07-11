import json
import os
import re
import argparse

def escape_latex(text):
    """
    Escapes special LaTeX characters in a given string.
    """
    if not isinstance(text, str):
        return ""
    return re.sub(r'([&%$#_{}])', r'\\\1', text)

def format_tex_display_math(text):
    """
    Formats a string for LaTeX display math, removing existing delimiters.
    """
    if not isinstance(text, str):
        return ""
    
    text = text.strip()
    
    # More robustly remove existing math delimiters using regex
    text = re.sub(r'^\\\[(.*)\\\]$', r'\1', text).strip() # unwrap \[...\]
    text = re.sub(r'^\\\((.*)\\\)$', r'\1', text).strip() # unwrap \(...\)
    text = re.sub(r'^\$\$(.*)\$\$$', r'\1', text).strip() # unwrap $$...$$
    text = re.sub(r'^\$(.*)\$$', r'\1', text).strip()     # unwrap $...$
        
    return f"\\[ {text} \\]"

TEX_TEMPLATE_HEADER = r"""
\documentclass[10pt]{article}
\usepackage[utf8]{inputenc}
\usepackage{amsmath}
\usepackage{amssymb}
\usepackage{geometry}
\usepackage{xcolor}
\usepackage{longtable}
\usepackage{array}
\usepackage{lmodern}

\geometry{a4paper, margin=1in}

\definecolor{pass}{HTML}{28a745}
\definecolor{fail}{HTML}{DC3545}

\title{Problem Refinement Critiques Report}
\author{Generated by script}
\date{\today}

\begin{document}
\maketitle
"""

TEX_TEMPLATE_FOOTER = r"""
\end{document}
"""

def generate_summary_table(critiques_data):
    """Generates summary statistics from the critiques."""
    stats = {
        "self_containment": {"pass": 0, "fail": 0},
        "difficulty": {"pass": 0, "fail": 0, "removed": 0},
        "useful_derivation": {"pass": 0, "fail": 0, "removed": 0},
        "refinement": {"success": 0, "fail": 0}
    }
    
    for critique_entry in critiques_data:
        critiques = critique_entry.get("critiques", {})
        is_removed = critique_entry.get("removed", False)
        
        # Check self-containment
        if "self_containment" in critiques and isinstance(critiques["self_containment"], dict):
            if critiques["self_containment"].get("is_self_contained", False):
                stats["self_containment"]["pass"] += 1
            else:
                stats["self_containment"]["fail"] += 1
        
        # Check difficulty
        if "difficulty" in critiques and isinstance(critiques["difficulty"], dict):
            if is_removed:
                stats["difficulty"]["removed"] += 1
            elif critiques["difficulty"].get("is_non_trivial", False):
                stats["difficulty"]["pass"] += 1
            else:
                stats["difficulty"]["fail"] += 1

        if "useful_derivation" in critiques and isinstance(critiques["useful_derivation"], dict):
            if is_removed and not critiques["useful_derivation"].get("is_useful_derivation", True):
                stats["useful_derivation"]["removed"] += 1
            elif critiques["useful_derivation"].get("is_useful_derivation", False):
                stats["useful_derivation"]["pass"] += 1
            else:
                stats["useful_derivation"]["fail"] += 1
        
        # Check refinement success (only for non-removed problems)
        if not is_removed:
            refined = critique_entry.get("refined_problem", {})
            if isinstance(refined, dict) and "error" not in refined:
                stats["refinement"]["success"] += 1
            else:
                stats["refinement"]["fail"] += 1
    
    # Generate summary table
    summary_tex = r"""
\section*{Summary Statistics}
\begin{center}
\begin{longtable}{|l|c|c|c|c|}
\hline
\textbf{Critique Type} & \textbf{Pass} & \textbf{Fail} & \textbf{Removed} & \textbf{Pass Rate} \\
\hline
\endfirsthead
\hline
\endfoot
"""
    
    for critique_type, counts in stats.items():
        if critique_type == "refinement":
            type_name = "Refinement Success"
            pass_count = counts["success"]
            fail_count = counts["fail"]
            removed_count = 0
        else:
            type_name = escape_latex(critique_type.replace("_", " ").title())
            pass_count = counts["pass"]
            fail_count = counts["fail"]
            removed_count = counts.get("removed", 0)
        
        total = pass_count + fail_count + removed_count
        pass_rate = f"{(pass_count / total * 100):.1f}\\%" if total > 0 else "N/A"
        
        summary_tex += f"{type_name} & {pass_count} & {fail_count} & {removed_count} & {pass_rate} \\\\\n"
    
    summary_tex += r"""\hline
\end{longtable}
\end{center}
"""
    
    return summary_tex

def format_critique_section(critique_type, critique_data):
    """Formats a single critique section."""
    tex = ""
    
    if isinstance(critique_data, dict) and "error" not in critique_data:
        # Check the boolean status
        if critique_type == "self_containment":
            status = critique_data.get("is_self_contained", False)
            status_text = "Self-contained" if status else "Not self-contained"
        elif critique_type == "difficulty":
            status = critique_data.get("is_non_trivial", False)
            status_text = "Non-trivial" if status else "Trivial"
        elif critique_type == "useful_derivation":
            status = critique_data.get("is_useful_derivation", False)
            status_text = "Useful" if status else "Useless"
        else:
            status = False
            status_text = "Unknown"
        
        color = "pass" if status else "fail"
        tex += f"\\textcolor{{{color}}}{{\\textbf{{Status: {status_text}}}}}\n\n"
        
        # Add the critique summary - no escaping, it may contain LaTeX
        critique_text = critique_data.get("critique", "No critique provided")
        tex += f"{critique_text}\n\n"
        
        # Add issues if any
        issues = critique_data.get("issues", [])
        if issues:
            tex += "\\textbf{Issues found:}\n"
            tex += "\\begin{itemize}\n"
            for issue in issues:
                # Don't escape finding and suggestion - they contain LaTeX math
                finding = issue.get("finding", "")
                suggestion = issue.get("suggestion", "")
                tex += f"\\item \\textbf{{Finding:}} {finding}\\\\\n"
                tex += f"\\textbf{{Suggestion:}} {suggestion}\n"
            tex += "\\end{itemize}\n"
    else:
        # Error case
        tex += "\\textcolor{fail}{\\textbf{Error parsing critique}}\n\n"
    
    return tex

def generate_critiques_section(critiques_data):
    """Generates the LaTeX for all critiques."""
    critiques_tex = "\\section*{Problem Details}\n\n"
    
    for i, critique_entry in enumerate(critiques_data):
        paper_id = escape_latex(critique_entry.get("paper_id", "N/A"))
        problem_index = critique_entry.get("problem_index", 0)
        
        critiques_tex += f"\\subsection*{{Problem {i+1} (Paper: {paper_id}, Index: {problem_index})}}\n\n"
        
        # Original problem
        original = critique_entry.get("original_problem", {})
        critiques_tex += "\\subsubsection*{Original Problem Statement}\n"
        problem_statement = original.get('problem_statement', 'No problem statement')
        critiques_tex += f"{problem_statement}\n\n"
        
        critiques_tex += "\\subsubsection*{Original Solution}\n"
        final_solution = original.get('final_solution', 'No solution')
        
        # Fix for multi-line boxed commands: ensure they're on one line
        if '\\boxed{' in final_solution:
            # Check if the boxed command spans multiple lines
            if final_solution.count('{') != final_solution.count('}'):
                # Try to fix by adding missing braces
                open_count = final_solution.count('{')
                close_count = final_solution.count('}')
                if open_count > close_count:
                    final_solution += '}' * (open_count - close_count)
        
        critiques_tex += f"{format_tex_display_math(final_solution)}\n\n"
        
        # Critiques
        critiques_tex += "\\subsubsection*{Critiques}\n"
        
        critiques = critique_entry.get("critiques", {})
        
        # Self-containment critique
        if "self_containment" in critiques:
            critiques_tex += "\\paragraph*{Self-Containment Critique:}\n"
            critiques_tex += format_critique_section("self_containment", critiques["self_containment"])
            critiques_tex += "\n"
        
        # Difficulty critique
        if "difficulty" in critiques:
            critiques_tex += "\\paragraph*{Difficulty Critique:}\n"
            critiques_tex += format_critique_section("difficulty", critiques["difficulty"])
            critiques_tex += "\n"

        if "useful_derivation" in critiques:
            critiques_tex += "\\paragraph*{Useful Derivation Critique:}\n"
            critiques_tex += format_critique_section("useful_derivation", critiques["useful_derivation"])
            critiques_tex += "\n"
        
        # Refined problem
        refined = critique_entry.get("refined_problem", {})
        is_removed = critique_entry.get("removed", False)
        included_in_dataset = critique_entry.get("included_in_dataset", True)
        
        if is_removed:
            critiques_tex += "\\subsubsection*{Problem Status}\n"
            critiques_tex += "\\textcolor{fail}{\\textbf{REMOVED: " + escape_latex(critique_entry.get("removal_reason", "Marked for removal")) + "}}\n\n"
        elif not included_in_dataset:
            critiques_tex += "\\subsubsection*{Problem Status}\n"
            critiques_tex += "\\textcolor{fail}{\\textbf{EXCLUDED: Trivial problem - refinement failed}}\n\n"
        else:
            critiques_tex += "\\subsubsection*{Refined Problem}\n"
            
            if isinstance(refined, dict) and "error" not in refined:
                # Handle different possible keys for the problem statement
                problem_key = "problem_statement" if "problem_statement" in refined else "question"
                solution_key = "final_solution" if "final_solution" in refined else "answer"
                
                critiques_tex += "\\paragraph*{Refined Problem Statement:}\n"
                refined_problem = refined.get(problem_key, 'No refined problem statement')
                critiques_tex += f"{refined_problem}\n\n"
                
                critiques_tex += "\\paragraph*{Refined Solution:}\n"
                refined_solution = refined.get(solution_key, 'No solution')
                
                # Fix for multi-line boxed commands in refined solution too
                if '\\boxed{' in refined_solution:
                    # Check if the boxed command spans multiple lines
                    if refined_solution.count('{') != refined_solution.count('}'):
                        # Try to fix by adding missing braces
                        open_count = refined_solution.count('{')
                        close_count = refined_solution.count('}')
                        if open_count > close_count:
                            refined_solution += '}' * (open_count - close_count)
                
                critiques_tex += f"{format_tex_display_math(refined_solution)}\n\n"
            else:
                critiques_tex += "\\textcolor{fail}{\\textbf{Error refining problem}}\n\n"
        
        critiques_tex += "\\newpage\n"
    
    return critiques_tex

def export_critiques_to_tex(critiques_file, output_tex_file):
    """
    Reads critiques and generates a LaTeX report.
    """
    if not os.path.exists(critiques_file):
        print(f"Error: Critiques file not found at '{critiques_file}'")
        return

    with open(critiques_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Generate content
    summary_tex = generate_summary_table(data)
    critiques_section_tex = generate_critiques_section(data)

    # Combine all parts
    final_tex = TEX_TEMPLATE_HEADER
    final_tex += summary_tex
    final_tex += critiques_section_tex
    final_tex += TEX_TEMPLATE_FOOTER

    # Write to file
    with open(output_tex_file, 'w', encoding='utf-8') as f:
        f.write(final_tex)

    print(f"LaTeX critiques report successfully generated at '{output_tex_file}'")
    print("You can now compile this file using a LaTeX distribution (like pdflatex) to create a PDF.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export problem critiques to LaTeX")
    parser.add_argument(
        "--critiques-file", 
        type=str, 
        default="output/critiques/all_critiques.json", 
        help="Path to the critiques JSON file"
    )
    parser.add_argument(
        "--output-tex-file", 
        type=str, 
        default="output/critiques/critiques_report.tex", 
        help="Path to the output LaTeX file"
    )
    args = parser.parse_args()

    export_critiques_to_tex(args.critiques_file, args.output_tex_file) 