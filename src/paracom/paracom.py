import re
import sys
import argparse
import os
from collections import Counter
from typing import List, Tuple, Optional

from ollama import chat, ChatResponse
from tqdm import tqdm

try:
    from .__about__ import __version__
except:
    __version__ = "(unknown)"

MODEL: str = "gemma3:12b"
NUM_CTX: int = 10000
TARGET_PARAGRAPH_LENGTH: int = 400
MAX_SINGLE_LINE_LENGTH: int = 200


def split_long_line_by_llm(line: str, max_length: int = 200) -> List[str]:
    """
    Use the LLM to split a line longer than max_length into segments.
    Splits are made at appropriate sentence boundaries so that each segment is within max_length.
    The LLM returns the segments as newline-separated text.
    """
    if len(line) <= max_length:
        return [line]
    prompt = (
        f"Please divide the following text into segments of {max_length} characters or less. "
        f"Ensure the divisions occur at appropriate sentence endings, and that each segment remains within the {max_length}-character limit.\n"
        "Return the output as a text with each segment separated by a newline.\n\n"
        f"{line}"
    )
    response: ChatResponse = chat(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        options={"num_ctx": NUM_CTX},
    )
    content: str = response["message"]["content"]
    segments: List[str] = [seg.strip() for seg in content.splitlines() if seg.strip()]
    return segments


def split_long_lines(lines: List[str], max_length: int = 200, verbose: bool = False) -> List[str]:
    """
    For each line in the input list, if it exceeds max_length, use the LLM to split it.
    Returns a list of processed lines.
    """

    bar = None
    if verbose:
        count_split_tasks = len(list(line for line in lines if len(line) > max_length))
        if count_split_tasks > 0:
            print("Info: Splitting long lines", file=sys.stderr)
            bar = tqdm(total=count_split_tasks)

    done = 0
    processed: List[str] = []
    for line in lines:
        if len(line) <= max_length:
            processed.append(line)
        else:
            segments: List[str] = split_long_line_by_llm(line, max_length)
            processed.extend(segments)
            done += 1
            if bar is not None:
                bar.update(done)
    if bar is not None:
        bar.close()
    return processed


def add_line_numbers(lines: List[str]) -> str:
    """
    Prepend each line with its line number in the format "number: content" and return the combined text.
    """
    numbered_lines = [f"{i+1}: {line}" for i, line in enumerate(lines)]
    return "\n".join(numbered_lines)


def split_nl_into_windows(
    number_and_lines: List[Tuple[int, str]], window_size: int, overlap: int
) -> List[List[Tuple[int, str]]]:
    """
    Split a list of (line_number, text) tuples into windows with the specified window_size and overlap.
    """
    windows: List[List[Tuple[int, str]]] = []
    i: int = 0
    while i < len(number_and_lines):
        window: List[Tuple[int, str]] = number_and_lines[i : i + window_size]
        windows.append(window)
        if i + window_size >= len(number_and_lines):
            break
        i += window_size - overlap
    return windows


def detect_conversation_turns_single(
    lines: List[str],
    window_size: int = 30,
    overlap: int = 10,
    boundary_margin: int = 5,
    skip_line_prefixes: List[str] = [],
    verbose: bool = False,
) -> List[int]:
    """
    Detect conversation-turn line numbers in a single run.
    The input is a list of lines. Windows are created based on window_size and overlap.
    In each window, line numbers within boundary_margin of the window's start or end are ignored.
    Lines that start with any prefix in skip_line_prefixes are excluded.
    Returns a sorted list of detected line numbers.
    """
    number_and_lines: List[Tuple[int, str]] = [
        (i + 1, line) for i, line in enumerate(lines)
    ]
    filtered_number_and_lines: List[Tuple[int, str]] = []
    for num, line in number_and_lines:
        if line and not any(line.startswith(prefix) for prefix in skip_line_prefixes):
            filtered_number_and_lines.append((num, line))

    windows: List[List[Tuple[int, str]]] = split_nl_into_windows(
        filtered_number_and_lines, window_size, overlap
    )
    detected_turns: set[int] = set()

    if verbose:
        window_iter = tqdm(enumerate(windows), total=len(windows))
    else:
        window_iter = enumerate(windows)

    for wi, window in window_iter:
        if not window:
            continue
        try:
            first_line_num: int = window[0][0]
            last_line_num: int = window[-1][0]
        except ValueError:
            continue

        lower_bound: int = (
            first_line_num + boundary_margin if wi != 0 else first_line_num
        )
        upper_bound: int = (
            last_line_num - boundary_margin if wi != len(windows) - 1 else last_line_num
        )

        window_line_set = {num for num, _ in window}
        window_text: str = "\n".join(f"{num}: {line}" for num, line in window)
        prompt = (
            "Identify the starting lines of paragraphs in the following conversation transcript.\n"
            "Exclude lines that cover the same topic as the previous line.\n"
            f"Ensure each paragraph has approximately {TARGET_PARAGRAPH_LENGTH} characters and do not make paragraphs that are too short.\n"
            "No explanations needed.\n"
            "Output a comma-separated list of line numbers.\n"
            "For example, if lines 15, 19, and 22 are suitable as the starting lines of paragraphs, output them as:\n"
            "15, 19, 22\n\n"
            f"{window_text}"
        )

        nums: Optional[List[int]] = None
        for attempt in range(5):
            response: ChatResponse = chat(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                options={"num_ctx": NUM_CTX},
            )
            content: str = response["message"]["content"]
            if verbose:
                print(f"Info: Response content: {content!r}", file=sys.stderr)

            # Try comma-separated output (e.g. "5, 23, 45")
            csv_lines: List[str] = []
            for cl in content.split("\n"):
                if re.match(r"^\d+(,\s*\d+)*$", cl):
                    csv_lines.append(cl)
            if len(csv_lines) == 1:
                nums = [int(numstr) for numstr in csv_lines[0].split(",")]
                break

            # Try line-by-line output (e.g. "5\n23\n45")
            cl = content.replace("\n", ",")
            if re.match(r"^\d+(,\s*\d+)*$", cl):
                nums = [int(numstr) for numstr in cl.split(",")]
                break

        if nums is None:
            continue

        for num in nums:
            if num in window_line_set and lower_bound <= num <= upper_bound:
                detected_turns.add(num)

    return sorted(detected_turns)


def insert_blank_lines(lines: List[str], turn_points: List[int]) -> str:
    """
    Inserts a blank line before each detected conversation-turn (using 1-indexed line numbers)
    in the original text. Blank lines act as paragraph separators.
    Returns the modified text.
    """
    output_lines: List[str] = []
    turn_set = set(turn_points)
    for idx, line in enumerate(lines, start=1):
        if idx in turn_set:
            output_lines.append("")
        output_lines.append(line)
    return "\n".join(output_lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Use an LLM to detect conversation turns in a transcript and insert blank lines as paragraph breaks."
    )
    parser.add_argument(
        "input_file", help="Input text file (use '-' to read from standard input)"
    )
    parser.add_argument(
        "-p", "--skip-line-prefix",
        action="append",
        default=[],
        help="Line prefix to exclude from detection. Can be specified multiple times.",
    )
    parser.add_argument(
        "-t", "--trials",
        type=int,
        default=1,
        help="Number of detection trials to run (default is 1; use 5 to merge results from 5 runs).",
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Output verbose log messages to stderr."
    )
    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument("-o", "--output", type=str, help="Output file name.")
    output_group.add_argument(
        "-O",
        "--auto-output",
        action="store_true",
        help="Automatically generate an output file name based on the input file name (appends '-paracom').",
    )
    parser.add_argument(
        "--version", action="version", version="%(prog)s " + __version__
    )
    args = parser.parse_args()

    # Read input from file or standard input
    if args.input_file == "-":
        input_lines = [line.rstrip() for line in sys.stdin.readlines() if line.rstrip()]
    else:
        try:
            with open(args.input_file, encoding="utf-8") as f:
                input_lines = [line.rstrip() for line in f.readlines() if line.rstrip()]
        except Exception as e:
            sys.exit(f"Error reading input file: {e}")

    # Process long lines using the LLM if they exceed MAX_SINGLE_LINE_LENGTH characters.
    processed_lines = split_long_lines(input_lines, max_length=MAX_SINGLE_LINE_LENGTH, verbose=args.verbose)

    # Run detection trials (default is 1 trial; if more than 1, merge results)
    if args.trials <= 1:
        final_turn_points = detect_conversation_turns_single(
            processed_lines,
            skip_line_prefixes=args.skip_line_prefix,
            verbose=args.verbose,
        )
    else:
        trial_results: List[List[int]] = []
        for i in range(args.trials):
            trial = detect_conversation_turns_single(
                processed_lines,
                skip_line_prefixes=args.skip_line_prefix,
                verbose=args.verbose,
            )
            trial_results.append(trial)
        counter = Counter()
        for trial in trial_results:
            counter.update(trial)
        # Use a threshold: at least (trials // 2 + 1) occurrences.
        threshold = args.trials // 2 + 1
        final_turn_points = sorted(
            [num for num, count in counter.items() if count >= threshold]
        )

    if args.verbose:
        print(f"Info: Final detected turn points: {final_turn_points}", file=sys.stderr)

    final_text = insert_blank_lines(processed_lines, final_turn_points)

    # Determine output destination
    if args.input_file == "-" and args.auto_output:
        sys.exit("Error: Cannot use -O/--auto-output when reading from standard input.")
    if args.auto_output:
        base, ext = os.path.splitext(args.input_file)
        output_filename = f"{base}-paracom{ext if ext else '.txt'}"
    elif args.output:
        output_filename = args.output
    else:
        output_filename = None

    if output_filename:
        try:
            with open(output_filename, "w", encoding="utf-8") as f:
                f.write(final_text)
            if args.verbose:
                print(f"Info: Output written to {output_filename}", file=sys.stderr)
        except Exception as e:
            sys.exit(f"Error writing output file: {e}")
    else:
        print(final_text)


if __name__ == "__main__":
    main()
