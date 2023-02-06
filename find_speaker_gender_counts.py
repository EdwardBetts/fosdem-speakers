#!/usr/bin/python3

# Written by Edward Betts <edward@4angle.com>
# The author disclaims all copyright. The software is in the public domain.

import collections
import os
import re
import time
from typing import Counter, Iterable

import gender_guesser.detector
import nameparser
import requests

year = "2023"

d = gender_guesser.detector.Detector()

re_he = re.compile(r"\b(he|him)\b", re.I)
re_she = re.compile(r"\b(she|her)\b", re.I)


def get_first_name(name: str) -> str:
    """Extract the first name."""
    first: str = nameparser.HumanName(name).first if " " in name else name
    return first


def guess_gender_from_bio(bio: str) -> str | None:
    """Guess gender based on personal pronouns in biography.

    If the bio contains 'she' or 'her' return 'female', alternatively if it
    contains 'he' or 'him' return 'male'.

    If the bio is empty or matches the conditions for both genders then return None.
    """
    if not bio:
        return None
    m_he, m_she = re_he.search(bio), re_she.search(bio)

    if m_he and not m_she:
        return "male"

    if m_she and not m_he:
        return "female"

    return None


def iter_speakers() -> Iterable[tuple[str, str]]:
    """Read speakers list page and yield slug and name for each speaker."""
    re_speaker_link = re.compile(
        r'^ +<li><a href="/(?:\d{4})/schedule/speaker/([^/]+)/">(.*)</a></li>$'
    )

    for line in open("speakers.html"):
        if not (m := re_speaker_link.match(line)):
            continue
        slug, name = m.groups()
        if slug == "fosdem_staff":
            continue
        yield slug, name


def get_speaker_pages() -> int:
    """Parse speakers.html and download speaker biographies in HTML."""
    total = 0
    for slug, name in iter_speakers():
        total += 1
        filename = f"html/{slug}.html"
        if os.path.exists(filename):
            continue
        print("downloading speaker page:", slug, name)
        url = f"https://fosdem.org/{year}/schedule/speaker/{slug}/"

        r = requests.get(url)
        with open(filename, "w") as out:
            out.write(r.text)
        time.sleep(0.2)

    return total


def parse_speaker_bio(filename: str) -> str:
    """Extract speaker biography from saved copy of the speaker page."""
    found_h1 = False
    bio_started = False
    bio = ""
    for line in open(filename):
        if not found_h1:
            if "<h1>" in line:
                found_h1 = True
            continue
        if line.startswith("<p>"):
            bio_started = True
        if not bio_started:
            continue
        if line.startswith('<br style="clear: both;"/>'):
            break

        bio += line

    return bio.strip()


def get_counts() -> dict[str, int]:
    """Calculate speaker gender counts."""
    counts: collections.Counter[str] = Counter()

    for slug, name in iter_speakers():
        filename = f"html/{slug}.html"
        bio = parse_speaker_bio(filename)
        gender_from_bio = guess_gender_from_bio(bio)
        if gender_from_bio:
            counts[gender_from_bio] += 1
            continue

        gender = d.get_gender(get_first_name(name))
        assert gender

        if gender.startswith("mostly_"):
            gender = gender[len("mostly_") :]
        if gender == "andy":
            gender = "unknown"
        counts[gender] += 1

    return dict(counts)


def main() -> None:
    """Download speaker biographies and generate a guess of gender counts."""
    if not os.path.exists("html"):
        os.mkdir("html")

    speakers_filename = "speakers.html"
    if not os.path.exists(speakers_filename):
        html = requests.get(f"https://fosdem.org/{year}/schedule/speakers/").text
        open(speakers_filename, "w").write(html)
    total = get_speaker_pages()
    counts = get_counts()
    print(total, "speakers")
    print(counts)


if __name__ == "__main__":
    main()
