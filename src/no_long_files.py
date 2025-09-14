import io
import os
from typing import Generator, Tuple, Type, List


class FileLengthChecker:
    """
    Flake8 plugin: enforce a maximum number of lines per file.

    Rule: FLN001
    - Triggers if the number of lines exceeds the configured limit.
    - Counting can ignore blank lines, comments, and the shebang line.
    """

    name = "flake8-file-length"
    version = "0.1.0"

    # Default values (overridden via parse_options)
    max_file_length: int = 400
    ignore_blank: bool = False
    ignore_comments: bool = False
    ignore_shebang: bool = True

    ERROR_CODE = "FLN001"
    ERROR_MSG = "FLN001 file too long: {count} lines (limit {limit}){suffix}"

    def __init__(self, tree, filename: str):
        # Flake8 passes `tree` and `filename`. We only need the filename.
        self.filename = filename

    # ---- Flake8 options integration --------------------------------------
    @classmethod
    def add_options(cls: Type["FileLengthChecker"], parser) -> None:
        parser.add_option(
            "--max-file-length",
            type=int,
            default=cls.max_file_length,
            parse_from_config=True,
            help="Maximum file length (lines). Default: 400",
        )
        parser.add_option(
            "--file-length-ignore-blank",
            action="store_true",
            default=cls.ignore_blank,
            parse_from_config=True,
            help="Ignore blank lines when counting.",
        )
        parser.add_option(
            "--file-length-ignore-comments",
            action="store_true",
            default=cls.ignore_comments,
            parse_from_config=True,
            help="Ignore comment lines starting with '#'.",
        )
        parser.add_option(
            "--file-length-ignore-shebang",
            action="store_true",
            default=cls.ignore_shebang,
            parse_from_config=True,
            help="Ignore the first shebang line (#!...).",
        )

    @classmethod
    def parse_options(cls: Type["FileLengthChecker"], options) -> None:
        cls.max_file_length = int(options.max_file_length)
        cls.ignore_blank = bool(options.file_length_ignore_blank)
        cls.ignore_comments = bool(options.file_length_ignore_comments)
        cls.ignore_shebang = bool(options.file_length_ignore_shebang)

    # ---- Core check ------------------------------------------------------
    def run(self) -> Generator[Tuple[int, int, str, Type["FileLengthChecker"]], None, None]:
        path = self.filename

        # Flake8 can pass "stdin" when analyzing piped code: safely ignore.
        if not path or path == "stdin" or not os.path.exists(path):
            return

        lines, total = self._read_lines(path)
        effective = self._count_effective_lines(lines)

        use_effective = self.ignore_blank or self.ignore_comments or self.ignore_shebang
        count = effective if use_effective else total

        if count > self.max_file_length:
            suffix = f" — total={total}, effective={effective}" if use_effective else ""
            msg = self.ERROR_MSG.format(count=count, limit=self.max_file_length, suffix=suffix)
            # Report at the first line of the file
            yield (1, 0, msg, type(self))

    # ---- Helpers ---------------------------------------------------------
    def _read_lines(self, path: str) -> Tuple[List[str], int]:
        """
        Read the file in UTF-8, replacing invalid characters.
        Always returns (lines, total_line_count).
        """
        try:
            with io.open(path, "r", encoding="utf-8", errors="replace", newline="") as f:
                text = f.read()
        except Exception:
            text = ""
        lines = text.splitlines()
        return lines, len(lines)

    def _count_effective_lines(self, lines: List[str]) -> int:
        count = 0
        for idx, line in enumerate(lines, start=1):
            if self.ignore_shebang and idx == 1 and line.lstrip().startswith("#!"):
                continue
            if self.ignore_blank and line.strip() == "":
                continue
            if self.ignore_comments and line.lstrip().startswith("#"):
                continue
            count += 1
        return count
