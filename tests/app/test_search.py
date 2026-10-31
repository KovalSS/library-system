"""G9: пошук і фільтрація каталогу (REQ-F-043...046, LS-24)."""
import pytest


@pytest.fixture
def librarian(api):
    return api.create_librarian()[1]


@pytest.fixture
def catalog(api, librarian):
    """Невеликий каталог: два видання Шевченка (поезія) і одне Франка (повість)."""
    poetry, prose = api.genre("Поезія"), api.genre("Повість")
    kobzar = api.edition(librarian, author="Тарас Шевченко", title="Кобзар", year=1840, genreId=poetry["id"])
    haidamaky = api.edition(librarian, author="Тарас Шевченко", title="Гайдамаки", year=1841, genreId=poetry["id"])
    zakhar = api.edition(librarian, author="Іван Франко", title="Захар Беркут", year=1883, genreId=prose["id"])
    return {"kobzar": kobzar, "haidamaky": haidamaky, "zakhar": zakhar, "poetry": poetry, "prose": prose}


def titles(client, headers, **params):
    r = client.get("/editions", headers=headers, params=params)
    assert r.status_code == 200, r.text
    return [e["title"] for e in r.json()["items"]]


# --- REQ-F-043: комбінована фільтрація (перетин умов)
def test_filter_by_author(client, librarian, catalog, contract):
    r = client.get("/editions", headers=librarian, params={"author": "Шевченко"})

    contract(r, "searchEditions")
    assert sorted(e["title"] for e in r.json()["items"]) == ["Гайдамаки", "Кобзар"]


def test_filter_by_title_substring(client, librarian, catalog):
    assert titles(client, librarian, title="Беркут") == ["Захар Беркут"]


def test_filter_by_genre(client, librarian, catalog):
    assert titles(client, librarian, genreId=catalog["prose"]["id"]) == ["Захар Беркут"]


def test_filter_by_year(client, librarian, catalog):
    assert titles(client, librarian, year=1841) == ["Гайдамаки"]


def test_several_filters_narrow_to_intersection(client, librarian, catalog):
    assert titles(client, librarian, author="Шевченко", genreId=catalog["poetry"]["id"], year=1840) == ["Кобзар"]
    assert titles(client, librarian, author="Франко", genreId=catalog["poetry"]["id"]) == []


def test_without_filters_whole_catalog_is_returned(client, librarian, catalog, contract):
    r = client.get("/editions", headers=librarian)

    assert r.json()["total"] == 3


# --- REQ-F-044: лише наявні
def test_available_only_excludes_editions_without_available_copy(client, api, librarian, catalog):
    api.copy(librarian, catalog["kobzar"]["id"])                                   # доступний
    api.copy(librarian, catalog["haidamaky"]["id"], status="damaged")             # пошкоджений
    issued = api.copy(librarian, catalog["zakhar"]["id"])
    api.issue(librarian, api.reader()[0]["id"], issued["id"])                     # виданий

    assert titles(client, librarian, availableOnly="true") == ["Кобзар"]
    assert len(titles(client, librarian, availableOnly="false")) == 3


# --- REQ-F-045: сортування
def test_sort_by_title(client, librarian, catalog):
    assert titles(client, librarian, sort="title") == ["Гайдамаки", "Захар Беркут", "Кобзар"]
    assert titles(client, librarian, sort="title", order="desc") == ["Кобзар", "Захар Беркут", "Гайдамаки"]


def test_sort_by_year(client, librarian, catalog):
    assert titles(client, librarian, sort="year", order="desc") == ["Захар Беркут", "Гайдамаки", "Кобзар"]


def test_sort_by_popularity_uses_loans_of_all_time(client, api, librarian, catalog, clock):
    def lend(edition, times):
        for _ in range(times):
            copy = api.copy(librarian, edition["id"])
            loan = api.issue(librarian, api.reader()[0]["id"], copy["id"])
            api.give_back(librarian, loan["id"])
    lend(catalog["zakhar"], 3)
    lend(catalog["kobzar"], 1)
    clock.advance(days=400)                         # популярність — за весь час, не за останній період

    assert titles(client, librarian, sort="popularity", order="desc") == ["Захар Беркут", "Кобзар", "Гайдамаки"]


# --- REQ-F-046: пошук доступний усім ролям
def test_search_is_available_to_every_role(client, api, catalog):
    _, reader = api.reader()
    _, librarian = api.create_librarian()
    _, admin = api.create_admin()

    for headers in (reader, librarian, admin, api.chief):
        assert len(titles(client, headers, author="Шевченко")) == 2


def test_search_requires_authentication(client, catalog, contract):
    r = client.get("/editions")

    contract(r, "searchEditions")
    assert r.status_code == 401


# --- некоректні параметри (контракт)
@pytest.mark.parametrize("params", [{"year": "abc"}, {"sort": "price"}, {"order": "up"}, {"page": 0},
                                    {"pageSize": 1000}, {"availableOnly": "maybe"}])
def test_invalid_search_parameters_are_rejected(client, librarian, params, contract):
    r = client.get("/editions", headers=librarian, params=params)

    contract(r, "searchEditions")
    assert r.status_code == 400
    assert r.json()["code"] == "validation_failed"


def test_results_are_paginated(client, librarian, catalog):
    r = client.get("/editions", headers=librarian, params={"sort": "title", "pageSize": 2, "page": 2})

    assert r.json()["total"] == 3
    assert [e["title"] for e in r.json()["items"]] == ["Кобзар"]
