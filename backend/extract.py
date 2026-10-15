import json
import re
import sys
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

    for index, page in enumerate(document):
        page_text = page.get_text("text")
        text.append(page_text)
        pages.append(page_text)
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


def crossref_by_doi(doi):
    import requests

    url = f"https://api.crossref.org/works/{requests.utils.quote(doi, safe='')}"
    response = requests.get(url, timeout=12)
    if response.status_code != 200:
        return None

    message = response.json().get("message", {})
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
    return [normalize_text(part) for part in parts if normalize_text(part)]


def heuristic_result(parsed):
    text = parsed.get("full_text", "")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    title = parsed.get("title") or first_meaningful_line(text)
    authors = []

    if parsed.get("author"):
        authors = split_authors(parsed["author"])
    else:
        title_index = next((index for index, line in enumerate(lines) if line == title), 0)
        candidates = []
        for line in lines[title_index + 1 : title_index + 6]:
            if not line or len(line) > 240:
                break
            candidates.append(line)
        if candidates:
            authors = split_authors(" ".join(candidates[:3]))

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
