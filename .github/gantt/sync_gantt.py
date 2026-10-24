#!/usr/bin/env python3
"""Génère un Gantt Mermaid depuis les issues GitHub et marque les retards.

Plugin générique : dates dans le corps des tickets (modèle « Tâche ») et
milestones. Les issues ouvertes en retard reçoivent le label ``overdue`` et
un commentaire ; elles ne sont pas fermées.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

API_VERSION = "2022-11-28"
OVERDUE_LABEL = "overdue"
NO_GANTT_LABEL = "no-gantt"
OVERDUE_MARKER = "<!-- github-gantt:overdue -->"
GANTT_START = "<!-- GANTT:START -->"
GANTT_END = "<!-- GANTT:END -->"
DEFAULT_CONFIG = Path(".gantt.yml")
DEFAULT_UNPLANNED = "Hors jalon"
EMPTY_GANTT = (
    "*Aucune issue planifiée. Ajoutez des dates de début/fin "
    "via le modèle d’issue « Tâche ».*"
)
EMPTY_FIELD_VALUES = frozenset(
    {"", "_no response_", "n/a", "-", "none", "null"}
)
EXCLUDE_RE = re.compile(
    r"^-\s*\[[xX]\]\s*Exclure cette issue du Gantt\b",
    re.MULTILINE,
)
START_HEADINGS = ("Date de début", "Start date")
DUE_HEADINGS = ("Date de fin", "Date d'échéance", "Due date", "End date")
START_LINE_RE = re.compile(
    r"^(?:start|d[ée]but)\s*:\s*(\d{4}-\d{2}-\d{2})\b",
    re.IGNORECASE | re.MULTILINE,
)
DUE_LINE_RE = re.compile(
    r"^(?:due|fin|end|deadline|échéance|echeance)\s*:\s*(\d{4}-\d{2}-\d{2})\b",
    re.IGNORECASE | re.MULTILINE,
)


@dataclass
class Config:
    title: str
    files: list[Path]
    unplanned_section: str = DEFAULT_UNPLANNED


@dataclass
class Milestone:
    number: int
    title: str
    due: date | None
    state: str


@dataclass
class PlannedIssue:
    number: int
    title: str
    start: date
    due: date
    closed: bool
    overdue: bool
    has_overdue_label: bool
    milestone_number: int | None
    section: str


@dataclass
class GanttSection:
    title: str
    sort_key: tuple
    tasks: list[PlannedIssue] = field(default_factory=list)
    milestone: Milestone | None = None


class GitHubError(RuntimeError):
    """Erreur HTTP GitHub."""


class GitHub:
    def __init__(self, token: str, repo: str) -> None:
        self.token = token
        self.repo = repo
        self.base = f"https://api.github.com/repos/{repo}"

    def request(
        self,
        method: str,
        path: str,
        data: Any | None = None,
        *,
        allow_404: bool = False,
    ) -> Any:
        url = path if path.startswith("http") else self.base + path
        body = None if data is None else json.dumps(data).encode("utf-8")
        req = urllib.request.Request(url, data=body, method=method)
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("X-GitHub-Api-Version", API_VERSION)
        req.add_header("Authorization", f"Bearer {self.token}")
        req.add_header("User-Agent", "github-gantt")
        if body is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req) as resp:
                raw = resp.read()
                if not raw:
                    return None
                return json.loads(raw.decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            if allow_404 and exc.code == 404:
                return None
            raise GitHubError(f"{method} {url} → HTTP {exc.code}: {detail}") from exc

    def paginate(self, path: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        sep = "&" if "?" in path else "?"
        page = 1
        while True:
            chunk = self.request("GET", f"{path}{sep}per_page=100&page={page}")
            if not chunk:
                break
            items.extend(chunk)
            if len(chunk) < 100:
                break
            page += 1
        return items


def log(message: str) -> None:
    print(f"[INFO]  {message}")


def default_root() -> Path:
    here = Path(__file__).resolve()
    if here.parent.name == "gantt" and here.parent.parent.name == ".github":
        return here.parents[2]
    return Path.cwd()


def unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def parse_simple_yaml(text: str) -> dict[str, Any]:
    """Parse le sous-ensemble YAML utilisé par .gantt.yml (stdlib only)."""
    data: dict[str, Any] = {}
    current_list: str | None = None
    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()
        if indent > 0 and line.startswith("-") and current_list:
            data.setdefault(current_list, []).append(unquote(line[1:].strip()))
            continue
        current_list = None
        if ":" not in line:
            continue
        key, rest = line.split(":", 1)
        key = key.strip()
        rest = rest.strip()
        if rest == "" or rest == "[]":
            current_list = key
            data[key] = []
            continue
        data[key] = unquote(rest)
    return data


def load_config_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return parse_simple_yaml(path.read_text(encoding="utf-8"))


def flatten_files(values: list[str] | None) -> list[str]:
    if not values:
        return []
    files: list[str] = []
    for value in values:
        for part in value.split(","):
            item = part.strip()
            if item:
                files.append(item)
    return files


def build_config(
    *,
    root: Path,
    repo: str,
    file_data: dict[str, Any],
    title_arg: str | None,
    files_arg: list[str] | None,
) -> Config:
    env_title = os.environ.get("GANTT_TITLE")
    env_files = os.environ.get("GANTT_FILES")
    title = (
        title_arg
        or env_title
        or (str(file_data["title"]) if file_data.get("title") else None)
        or repo.split("/")[-1]
    )
    raw_files = flatten_files(files_arg)
    if not raw_files and env_files:
        raw_files = flatten_files([env_files])
    if not raw_files:
        listed = file_data.get("files")
        if isinstance(listed, list) and listed:
            raw_files = [str(item) for item in listed]
        elif isinstance(listed, str) and listed:
            raw_files = flatten_files([listed])
    if not raw_files:
        raw_files = ["README.md"]
    unplanned = str(file_data.get("unplanned_section") or DEFAULT_UNPLANNED)
    return Config(
        title=title,
        files=[Path(item) for item in raw_files],
        unplanned_section=unplanned,
    )


def parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    match = re.search(r"(\d{4}-\d{2}-\d{2})", value)
    if not match:
        return None
    try:
        return date.fromisoformat(match.group(1))
    except ValueError:
        return None


def heading_value(body: str, heading: str) -> str | None:
    pattern = rf"^###\s+{re.escape(heading)}\s*\n+([^\n#]+)"
    match = re.search(pattern, body, re.MULTILINE | re.IGNORECASE)
    if not match:
        return None
    value = match.group(1).strip()
    if value.lower() in EMPTY_FIELD_VALUES:
        return None
    return value


def parse_heading_date(body: str, headings: tuple[str, ...]) -> date | None:
    for heading in headings:
        value = heading_value(body, heading)
        parsed = parse_iso_date(value)
        if parsed:
            return parsed
    return None


def parse_issue_dates(body: str) -> tuple[date | None, date | None]:
    start = parse_heading_date(body, START_HEADINGS)
    due = parse_heading_date(body, DUE_HEADINGS)
    if start is None:
        match = START_LINE_RE.search(body)
        if match:
            start = date.fromisoformat(match.group(1))
    if due is None:
        match = DUE_LINE_RE.search(body)
        if match:
            due = date.fromisoformat(match.group(1))
    return start, due


def is_excluded(body: str, labels: set[str]) -> bool:
    if NO_GANTT_LABEL in labels:
        return True
    return bool(EXCLUDE_RE.search(body))


def mermaid_label(text: str, max_len: int = 48) -> str:
    cleaned = re.sub(r'[:;#`"<>{}[\]|]+', " ", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if len(cleaned) > max_len:
        cleaned = cleaned[: max_len - 1].rstrip() + "..."
    return cleaned or "tache"


def issue_labels(issue: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    for label in issue.get("labels") or []:
        if isinstance(label, str):
            names.add(label)
        elif isinstance(label, dict) and label.get("name"):
            names.add(str(label["name"]))
    return names


def detect_repo(explicit: str | None, root: Path) -> str:
    if explicit:
        return explicit.strip()
    env = os.environ.get("GITHUB_REPOSITORY")
    if env:
        return env.strip()
    try:
        raw = subprocess.check_output(
            ["git", "remote", "get-url", "origin"],
            cwd=root,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit(
            "Impossible de déterminer le dépôt. Passez --repo owner/name."
        ) from exc
    raw = re.sub(r"\.git$", "", raw)
    match = re.search(r"github\.com[:/]([^/]+/[^/]+)$", raw)
    if not match:
        raise SystemExit(f"Remote origin n'est pas un dépôt GitHub : {raw}")
    return match.group(1)


def token_from_env(explicit: str | None) -> str:
    if explicit:
        return explicit
    for key in ("GITHUB_TOKEN", "GH_TOKEN"):
        value = os.environ.get(key)
        if value:
            return value
    raise SystemExit(
        "Jeton GitHub manquant. Exportez GITHUB_TOKEN ou passez --token."
    )


def load_milestones(api: GitHub) -> dict[int, Milestone]:
    result: dict[int, Milestone] = {}
    for item in api.paginate("/milestones?state=all"):
        number = int(item["number"])
        result[number] = Milestone(
            number=number,
            title=str(item.get("title") or f"Milestone {number}"),
            due=parse_iso_date(item.get("due_on")),
            state=str(item.get("state") or "open"),
        )
    return result


def plan_issues(
    issues: list[dict[str, Any]],
    milestones: dict[int, Milestone],
    today: date,
    unplanned_section: str,
) -> list[PlannedIssue]:
    planned: list[PlannedIssue] = []
    for issue in issues:
        if issue.get("pull_request"):
            continue
        body = issue.get("body") or ""
        labels = issue_labels(issue)
        if is_excluded(body, labels):
            continue
        start, due = parse_issue_dates(body)
        milestone_data = issue.get("milestone") or {}
        milestone_number = (
            int(milestone_data["number"]) if milestone_data.get("number") else None
        )
        milestone = milestones.get(milestone_number) if milestone_number else None
        if due is None and milestone is not None:
            due = milestone.due
        if due is None:
            continue
        if start is None:
            start = parse_iso_date(issue.get("created_at")) or due
        if start > due:
            start = due
        closed = issue.get("state") == "closed"
        overdue = (not closed) and due < today
        section = milestone.title if milestone else unplanned_section
        planned.append(
            PlannedIssue(
                number=int(issue["number"]),
                title=str(issue.get("title") or f"Issue {issue['number']}"),
                start=start,
                due=due,
                closed=closed,
                overdue=overdue,
                has_overdue_label=OVERDUE_LABEL in labels,
                milestone_number=milestone_number,
                section=section,
            )
        )
    return planned


def build_sections(
    planned: list[PlannedIssue],
    milestones: dict[int, Milestone],
) -> list[GanttSection]:
    sections: dict[str, GanttSection] = {}

    def section_for(title: str, milestone: Milestone | None) -> GanttSection:
        if title not in sections:
            if milestone is None:
                sort_key = (1, date.max.isoformat(), title.lower())
            else:
                due_key = (
                    milestone.due.isoformat() if milestone.due else date.max.isoformat()
                )
                sort_key = (0, due_key, title.lower())
            sections[title] = GanttSection(
                title=title, sort_key=sort_key, milestone=milestone
            )
        elif milestone is not None:
            sections[title].milestone = milestone
        return sections[title]

    for item in planned:
        milestone = (
            milestones.get(item.milestone_number) if item.milestone_number else None
        )
        section_for(item.section, milestone).tasks.append(item)

    for milestone in milestones.values():
        if milestone.due is None:
            continue
        section_for(milestone.title, milestone)

    for section in sections.values():
        section.tasks.sort(key=lambda task: (task.start, task.due, task.number))

    return sorted(sections.values(), key=lambda section: section.sort_key)


def task_status(item: PlannedIssue) -> str:
    if item.closed:
        return "done"
    if item.overdue:
        return "crit"
    return "active"


def render_gantt(sections: list[GanttSection], title: str) -> str:
    has_content = any(section.tasks or section.milestone for section in sections)
    if not has_content:
        return EMPTY_GANTT

    lines = [
        "```mermaid",
        "gantt",
        f"    title {mermaid_label(title, 60)}",
        "    dateFormat YYYY-MM-DD",
        "    axisFormat %d/%m",
    ]
    for section in sections:
        if not section.tasks and not (section.milestone and section.milestone.due):
            continue
        lines.append(f"    section {mermaid_label(section.title, 40)}")
        for task in section.tasks:
            label = mermaid_label(f"{task.number} {task.title}")
            status = task_status(task)
            start = task.start.isoformat()
            due = task.due.isoformat()
            if task.start == task.due:
                lines.append(f"    {label} :{status}, i{task.number}, {start}, 1d")
            else:
                lines.append(f"    {label} :{status}, i{task.number}, {start}, {due}")
        milestone = section.milestone
        if milestone and milestone.due:
            label = mermaid_label(f"Jalon {milestone.title}")
            lines.append(
                f"    {label} :milestone, m{milestone.number}, "
                f"{milestone.due.isoformat()}, 1d"
            )
    lines.append("```")
    return "\n".join(lines)


def replace_markers(text: str, inner: str, path: Path) -> str:
    pattern = re.compile(
        re.escape(GANTT_START) + r".*?" + re.escape(GANTT_END),
        re.DOTALL,
    )
    replacement = f"{GANTT_START}\n{inner.rstrip()}\n{GANTT_END}"
    if not pattern.search(text):
        raise SystemExit(f"Marqueurs GANTT absents dans {path}")
    return pattern.sub(replacement, text, count=1)


def write_gantt_files(
    root: Path, files: list[Path], inner: str, dry_run: bool
) -> list[Path]:
    changed: list[Path] = []
    for relative in files:
        path = root / relative
        if not path.is_file():
            raise SystemExit(f"Fichier introuvable : {relative}")
        original = path.read_text(encoding="utf-8")
        updated = replace_markers(original, inner, relative)
        if updated == original:
            log(f"Inchangé : {relative}")
            continue
        if dry_run:
            log(f"[dry-run] Écrirait {relative}")
        else:
            path.write_text(updated, encoding="utf-8")
            log(f"Mis à jour : {relative}")
        changed.append(path)
    return changed


def ensure_labels(api: GitHub, dry_run: bool) -> None:
    specs = (
        (OVERDUE_LABEL, "B60205", "Échéance dépassée (Gantt)"),
        (NO_GANTT_LABEL, "EDEDED", "Exclure du Gantt"),
    )
    for name, color, description in specs:
        encoded = urllib.parse.quote(name, safe="")
        existing = api.request("GET", f"/labels/{encoded}", allow_404=True)
        if existing:
            continue
        if dry_run:
            log(f"[dry-run] Créerait le label {name}")
            continue
        try:
            api.request(
                "POST",
                "/labels",
                {"name": name, "color": color, "description": description},
            )
            log(f"Label créé : {name}")
        except GitHubError as exc:
            if "already_exists" in str(exc):
                continue
            raise


def issue_has_overdue_comment(api: GitHub, number: int) -> bool:
    comments = api.paginate(f"/issues/{number}/comments")
    return any(OVERDUE_MARKER in (comment.get("body") or "") for comment in comments)


def overdue_comment_body(item: PlannedIssue) -> str:
    return (
        f"{OVERDUE_MARKER}\n"
        f"Cette issue est en retard (échéance **{item.due.isoformat()}**). "
        f"Le label `{OVERDUE_LABEL}` a été ajouté. "
        "Elle n’a **pas** été fermée."
    )


def sync_overdue(api: GitHub, planned: list[PlannedIssue], dry_run: bool) -> None:
    ensure_labels(api, dry_run)
    encoded = urllib.parse.quote(OVERDUE_LABEL, safe="")
    for item in planned:
        if item.closed:
            if item.has_overdue_label:
                if dry_run:
                    log(f"[dry-run] Retirerait {OVERDUE_LABEL} de #{item.number} (fermée)")
                else:
                    api.request(
                        "DELETE",
                        f"/issues/{item.number}/labels/{encoded}",
                        allow_404=True,
                    )
                    log(f"Label {OVERDUE_LABEL} retiré de #{item.number} (fermée)")
            continue
        if item.overdue:
            if not item.has_overdue_label:
                if dry_run:
                    log(f"[dry-run] Ajouterait {OVERDUE_LABEL} à #{item.number}")
                else:
                    api.request(
                        "POST",
                        f"/issues/{item.number}/labels",
                        {"labels": [OVERDUE_LABEL]},
                    )
                    log(f"Label {OVERDUE_LABEL} ajouté à #{item.number}")
            if dry_run:
                log(f"[dry-run] Vérifierait le commentaire overdue de #{item.number}")
                continue
            if not issue_has_overdue_comment(api, item.number):
                api.request(
                    "POST",
                    f"/issues/{item.number}/comments",
                    {"body": overdue_comment_body(item)},
                )
                log(f"Commentaire overdue posté sur #{item.number}")
            continue
        if item.has_overdue_label:
            if dry_run:
                log(f"[dry-run] Retirerait {OVERDUE_LABEL} de #{item.number}")
            else:
                api.request(
                    "DELETE",
                    f"/issues/{item.number}/labels/{encoded}",
                    allow_404=True,
                )
                log(f"Label {OVERDUE_LABEL} retiré de #{item.number}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Génère un Gantt Mermaid depuis GitHub Issues (plugin github-gantt)."
    )
    parser.add_argument("--repo", help="owner/name (défaut: GITHUB_REPOSITORY ou origin)")
    parser.add_argument("--token", help="Défaut: GITHUB_TOKEN ou GH_TOKEN")
    parser.add_argument("--title", help="Titre du diagramme (défaut: .gantt.yml ou nom du repo)")
    parser.add_argument(
        "--files",
        action="append",
        help="Fichiers markdown à mettre à jour (répétable ou virgules)",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Fichier de config (défaut: <root>/.gantt.yml)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="N'écrit ni l'API GitHub ni les fichiers markdown",
    )
    parser.add_argument(
        "--no-commit-files",
        action="store_true",
        help="Ne pas écrire les markdown ; ne fait que le suivi overdue",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Racine du dépôt",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = (args.root or default_root()).resolve()
    repo = detect_repo(args.repo, root)
    token = token_from_env(args.token)
    config_path = args.config or (root / DEFAULT_CONFIG)
    if args.config:
        config_path = args.config if args.config.is_absolute() else root / args.config
    file_data = load_config_file(config_path)
    config = build_config(
        root=root,
        repo=repo,
        file_data=file_data,
        title_arg=args.title,
        files_arg=args.files,
    )
    today = datetime.now(timezone.utc).date()
    api = GitHub(token, repo)

    log(f"Dépôt {repo} — {today.isoformat()}")
    if config_path.is_file():
        log(f"Config {config_path}")
    log(f"Titre : {config.title}")
    milestones = load_milestones(api)
    issues = api.paginate("/issues?state=all")
    planned = plan_issues(issues, milestones, today, config.unplanned_section)
    log(f"{len(planned)} issue(s) planifiée(s), {len(milestones)} milestone(s)")

    inner = render_gantt(build_sections(planned, milestones), config.title)
    if args.dry_run:
        print(inner)
        print()

    sync_overdue(api, planned, dry_run=args.dry_run)

    if not args.no_commit_files:
        write_gantt_files(root, config.files, inner, dry_run=args.dry_run)
    elif args.dry_run:
        log("[dry-run] Fichiers markdown ignorés (--no-commit-files)")
    else:
        log("Fichiers markdown ignorés (--no-commit-files)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except GitHubError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
