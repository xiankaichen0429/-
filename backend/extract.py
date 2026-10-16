import json
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+\b")
ARXIV_NEW_RE = re.compile(r"arXiv:\s*(\d{4}\.\d{4,5})(?:v\d+)?", re.IGNORECASE)
ARXIV_OLD_RE = re.compile(r"arXiv:\s*([a-z\-]+/\d{7})(?:v\d+)?", re.IGNORECASE)
YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")


def normalize_text(value):
    return re.sub(r"\s+", " ", value or "").strip()


def extract_pdf(file_path):
    import fitz

    document = fitz.open(file_path)
    metadata = document.metadata or {}
    pages = []
    text = []
    layout_lines = []

    for index, page in enumerate(document):
        page_text = page.get_text("text")
        text.append(page_text)
        pages.append(page_text)
        if index == 0:
            page_dict = page.get_text("dict")
            for block in page_dict.get("blocks", []):
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    spans = line.get("spans", [])
                    line_text = "".join(span.get("text", "") for span in spans).strip()
                    if line_text:
                        max_size = max((span.get("size", 0) for span in spans), default=0)
                        layout_lines.append({"text": line_text, "size": max_size})
        if index >= 4:
            break

    document.close()
    full_text = "\n".join(text)
    return {
        "title": normalize_text(metadata.get("title")),
        "author": normalize_text(metadata.get("author")),
        "subject": normalize_text(metadata.get("subject")),
        "keywords": normalize_text(metadata.get("keywords")),
        "full_text": full_text,
        "first_page_text": pages[0] if pages else "",
        "layout_lines": layout_lines,
    }


def extract_docx(file_path):
    import docx

    document = docx.Document(file_path)
    paragraphs = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]
    full_text = "\n".join(paragraphs)
    core = document.core_properties

    return {
        "title": normalize_text(core.title),
        "author": normalize_text(core.author),
        "subject": normalize_text(core.subject),
        "keywords": normalize_text(core.keywords),
        "full_text": full_text,
        "first_page_text": full_text,
        "layout_lines": [],
    }


def find_doi(text):
    match = DOI_RE.search(text)
    if match:
        doi = match.group(0).strip(".,;")
        return doi
    return None


def find_arxiv(text):
    match = ARXIV_NEW_RE.search(text) or ARXIV_OLD_RE.search(text)
    return match.group(1) if match else None


def parse_crossref_message(message):
    if not message:
        return None

    authors = []
    for item in message.get("author", []):
        given = item.get("given", "")
        family = item.get("family", "")
        name = item.get("name", "")
        if name:
            authors.append(name)
        else:
            authors.append(" ".join([given, family]).strip())

    date_parts = []
    for key in ("published-print", "published-online", "issued"):
        value = message.get(key, {}).get("date-parts", [])
        if value and value[0]:
            date_parts = value[0]
            break

    year = str(date_parts[0]) if date_parts else ""

    return {
        "title": normalize_text((message.get("title") or [""])[0]),
        "authors": [normalize_text(author) for author in authors if normalize_text(author)],
        "year": year,
        "journal": normalize_text((message.get("container-title") or [""])[0]),
        "volume": normalize_text(message.get("volume")),
        "issue": normalize_text(message.get("issue")),
        "pages": normalize_text(message.get("page")),
        "doi": normalize_text(message.get("DOI")),
        "abstract": normalize_text(message.get("abstract")),
        "source": "crossref",
        "confidence": "high",
    }


def crossref_by_doi(doi):
    import requests

    url = f"https://api.crossref.org/works/{requests.utils.quote(doi, safe='')}"
    response = requests.get(url, timeout=12)
    if response.status_code != 200:
        return None

    return parse_crossref_message(response.json().get("message", {}))


def crossref_search(title, author=""):
    import requests

    params = {
        "query.title": title,
        "rows": 3,
    }
    if author:
        params["query.author"] = author

    try:
        response = requests.get("https://api.crossref.org/works", params=params, timeout=12)
    except requests.RequestException:
        return None

    if response.status_code != 200:
        return None

    items = response.json().get("message", {}).get("items", [])
    return parse_crossref_message(items[0]) if items else None


def first_meaningful_line(text):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines:
        lowered = line.lower()
        if len(line) < 4:
            continue
        if any(word in lowered for word in ("abstract", "摘要", "doi:", "arxiv:")):
            continue
        return line
    return ""


def split_authors(value):
    value = re.sub(r"\s+(and|&)\s+", ", ", value, flags=re.IGNORECASE)
    parts = re.split(r"[,，;；、]", value)
    result = []
    for part in parts:
        part = normalize_text(part)
        if not part:
            continue
        tokens = part.split()
        if len(tokens) > 1 and all(re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", token) for token in tokens):
            result.extend(tokens)
        else:
            result.append(part)
    return result


GENERIC_AUTHORS = {
    "lenovo",
    "user",
    "microsoft",
    "administrator",
    "author",
    "佚名",
    "unknown",
    "中国知网",
    "cnki",
}


def is_generic_author(value):
    lowered = value.lower()
    return lowered in GENERIC_AUTHORS or "@" in value or len(value) > 80


def clean_authors(values):
    return [value for value in values if value and not is_generic_author(value)]


def extract_explicit_authors(text):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    patterns = [
        r"^作者(?:信息|简介)?[:：]\s*(.+)$",
        r"^authors?\s*[:：]\s*(.+)$",
        r"^by\s*[:：]?\s*(.+)$",
    ]

    for line in lines:
        for pattern in patterns:
            match = re.match(pattern, line, re.IGNORECASE)
            if not match:
                continue

            value = match.group(1).strip()
            value = re.sub(r"[\[\(（].*?[\]\)）]", " ", value)
            value = re.sub(r"[*†‡#\d]+", " ", value)

            affiliation_match = re.search(
                r"(学院|大学|实验室|实验中心|中心|研究院|研究所|邮箱|E-mail|Email|通讯作者|作者简介|研究方向|二0|二O|20\d{2}|20\d{2}年)",
                value,
                re.IGNORECASE,
            )
            if affiliation_match:
                value = value[: affiliation_match.start()]

            authors = clean_authors(split_authors(value))
            if authors:
                return authors

    return []


def layout_title_and_authors(layout_lines):
    if not layout_lines:
        return "", []

    sizes = [line["size"] for line in layout_lines if line["text"]]
    if not sizes:
        return "", []

    max_size = max(sizes)
    title_candidates = [
        line
        for line in layout_lines
        if line["text"] and line["size"] >= max_size - 0.5 and len(line["text"]) >= 4
    ]

    if not title_candidates:
        return "", []

    title = " ".join(line["text"] for line in title_candidates[:2])
    first_title_index = layout_lines.index(title_candidates[0])
    author_lines = []

    for line in layout_lines[first_title_index + 1 : first_title_index + 5]:
        if not line["text"]:
            continue
        lowered = line["text"].lower()
        if any(
            word in line["text"]
            for word in ("学院", "大学", "实验室", "实验中心", "中心", "二0", "年", "月")
        ):
            break
        if line["size"] < max_size * 0.38 or line["size"] > max_size * 1.05:
            break
        author_line = re.sub(r"^(主编|作者|编著|by|authors?)[:：]\s*", "", line["text"], flags=re.IGNORECASE)
        affiliation_match = re.search(
            r"(学院|大学|实验室|实验中心|中心|二0|二O|20\d{2}|20\d{2}年)",
            author_line,
        )
        if affiliation_match:
            author_line = author_line[: affiliation_match.start()]
        author_lines.append(author_line)

    authors = clean_authors(split_authors(" ".join(author_lines[:3])))
    return title, authors


def heuristic_result(parsed):
    text = parsed.get("full_text", "")
    layout_title, layout_authors = layout_title_and_authors(parsed.get("layout_lines", []))

    title = layout_title or parsed.get("title") or first_meaningful_line(text)
    if title.lower() in GENERIC_AUTHORS or len(title) < 4:
        title = first_meaningful_line(text)

    authors = extract_explicit_authors(text)
    if not authors:
        authors = layout_authors or clean_authors(split_authors(parsed.get("author", "")))
    if not authors:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        title_index = next((index for index, line in enumerate(lines) if line == title), 0)
        candidates = []
        for line in lines[title_index + 1 : title_index + 6]:
            if not line or len(line) > 240:
                break
            candidates.append(line)
        authors = clean_authors(split_authors(" ".join(candidates[:3])))

    year_match = YEAR_RE.search(parsed.get("subject") or text[:4000])
    year = year_match.group(0) if year_match else ""

    return {
        "title": title,
        "authors": authors[:12],
        "year": year,
        "journal": parsed.get("subject") or parsed.get("journal") or "",
        "volume": "",
        "issue": "",
        "pages": "",
        "doi": "",
        "abstract": "",
        "source": "heuristic",
        "confidence": "low",
    }


def normalized(value):
    return re.sub(r"[\W_]+", "", value or "").lower()


def titles_match(left, right):
    left_value = normalized(left)
    right_value = normalized(right)
    if not left_value or not right_value:
        return False
    if left_value == right_value:
        return True
    return SequenceMatcher(None, left_value[:80], right_value[:80]).ratio() >= 0.45


def search_by_title(title, authors):
    remote = crossref_search(title, authors[0] if authors else "")
    if remote and titles_match(title, remote.get("title", "")):
        return remote
    return None


def extract_file(file_path):
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        parsed = extract_pdf(str(path))
    elif suffix == ".docx":
        parsed = extract_docx(str(path))
    else:
        return {
            "title": path.stem,
            "authors": [],
            "year": "",
            "journal": "",
            "volume": "",
            "issue": "",
            "pages": "",
            "doi": "",
            "abstract": "",
            "source": "filename",
            "confidence": "none",
            "error": "暂不支持该文件格式，请使用 PDF 或 DOCX",
        }

    doi = find_doi(parsed.get("full_text", "")) or find_doi(parsed.get("title", ""))
    arxiv_id = find_arxiv(parsed.get("full_text", ""))

    if doi:
        remote = crossref_by_doi(doi)
        if remote:
            remote["full_text"] = parsed.get("full_text", "")[:5000]
            return remote

    result = heuristic_result(parsed)
    if arxiv_id:
        result["arxiv"] = arxiv_id

    if result.get("title"):
        remote = search_by_title(result["title"], result.get("authors", []))
        if remote:
            if arxiv_id:
                remote["arxiv"] = arxiv_id
            result = remote

    result["full_text"] = parsed.get("full_text", "")[:5000]

    return result


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "缺少文件路径"}, ensure_ascii=False))
        return 1

    result = extract_file(sys.argv[1])
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
