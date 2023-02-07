#!/usr/bin/python3

# Written by Edward Betts <edward@4angle.com>
# The author disclaims all copyright. The software is in the public domain.

import collections
import os
import re
import sys
import time
from typing import Counter, Iterable

import gender_guesser.detector
import nameparser
import requests

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


def iter_speakers(year: int) -> Iterable[tuple[str, str]]:
    """Read speakers list page and yield slug and name for each speaker."""
    re_speaker_link = re.compile(
        r'^ +<li><a href="/(?:\d{4})/schedule/speaker/([^/]+)/">(.*)</a></li>$'
    )

    for line in open(f"{year}/speakers.html"):
        if not (m := re_speaker_link.match(line)):
            continue
        slug, name = m.groups()
        if slug == "fosdem_staff":
            continue
        yield slug, name


def get_speaker_pages(year: int) -> int:
    """Parse speakers.html and download speaker biographies in HTML."""
    total = 0
    for slug, name in iter_speakers(year):
        total += 1
        filename = f"{year}/html/{slug}.html"
        if os.path.exists(filename):
            continue
        print("downloading speaker page:", slug, name)
        url = f"https://fosdem.org/{year}/schedule/speaker/{slug}/"

        r = requests.get(url)
        with open(filename, "wb") as out:
            out.write(r.content)
        time.sleep(0.05)

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


def get_speaker_tracks(filename: str) -> set[str]:
    """Parse speaker page to find the tracks for their talks."""
    tracks = set()
    re_track = re.compile(
        r'^ +<td><a href="/(?:\d+)/schedule/track/(.*)/">(.*)</a></td>$'
    )

    for line in open(filename):
        if not (m := re_track.match(line)):
            continue
        track, track_name = m.groups()
        if track == "test" or track.startswith("bofs_"):
            continue
        if track.startswith("main_track"):  # combine the two rooms for the main track
            track_name = "Main track"
        tracks.add(track_name)

    return tracks


def get_speaker_gender(year: int, slug: str, name: str) -> str:
    """Guess the gender of the speaker from the their biography or name."""
    filename = f"{year}/html/{slug}.html"
    bio = parse_speaker_bio(filename)
    gender_from_bio = guess_gender_from_bio(bio)
    if gender_from_bio:
        return gender_from_bio

    gender: str = d.get_gender(get_first_name(name))

    if gender.startswith("mostly_"):
        gender = gender[len("mostly_") :]
    if gender == "andy":
        gender = "unknown"

    return gender


def get_counts(year: int) -> dict[str, int]:
    """Calculate speaker gender counts."""
    counts: collections.Counter[str] = Counter()

    for slug, name in iter_speakers(year):
        counts[get_speaker_gender(year, slug, name)] += 1

    return dict(counts)


def mkdir(d: str) -> None:
    """Create a directory if it doesn't already exist."""
    if not os.path.exists(d):
        os.mkdir(d)


def process_year(year: int) -> None:
    """Download speaker biographies and generate a guess of gender counts."""
    mkdir(str(year))
    mkdir(f"{year}/html")

    speakers_filename = f"{year}/speakers.html"
    if not os.path.exists(speakers_filename):
        html = requests.get(f"https://fosdem.org/{year}/schedule/speakers/").content
        open(speakers_filename, "wb").write(html)
    total = get_speaker_pages(year)
    counts = get_counts(year)
    print(f"{year}: {total} speakers {get_ratio(counts):.2%} female")


def get_ratio(counts: dict[str, int]) -> float:
    """Calculate the percentage of speakers who are female."""
    male = counts.get("male", 0)
    female = counts.get("female", 0)

    return female / (male + female)


def get_tracks_and_gender(year: int) -> Iterable[tuple[str, str]]:
    """For every event yield the track and the speakers gender."""
    for slug, name in iter_speakers(year):
        filename = f"{year}/html/{slug}.html"
        tracks = get_speaker_tracks(filename)
        gender = get_speaker_gender(year, slug, name)
        for track in tracks:
            yield (track, gender)


def show_gender_diversity_by_track(year: int) -> None:
    """Show a list of speaking tracks with the percentage of female speakers."""
    count: collections.defaultdict[str, Counter[str]] = collections.defaultdict(Counter)
    for track, gender in get_tracks_and_gender(2023):
        count[track][gender] += 1

    tracks: list[tuple[float, str]] = []
    for track, counts in count.items():
        tracks.append((get_ratio(counts), track))

    tracks.sort(reverse=True)
    for ratio, track in tracks:
        print(f"{ratio:6.2%}  {track}")


def main() -> None:
    """Check gender ratios for FOSDEM speakers."""
    if len(sys.argv) > 1 and sys.argv[1] == "--tracks":
        year = int(sys.argv[2])
        return show_gender_diversity_by_track(year)

    for year in range(2023, 2012, -1):
        process_year(year)
        year -= 1


if __name__ == "__main__":
    main()
