"""G11: рекомендації (REQ-F-032...034, LS-26)."""
import pytest


@pytest.fixture
def librarian(api):
    return api.create_librarian()[1]


@pytest.fixture
def shelf(api, librarian):
    """Читач отримав «Кобзар» (Шевченко, поезія). Решта видань — кандидати для рекомендацій."""
    poetry, prose = api.genre("Поезія"), api.genre("Повість")

    def edition(author, title, genre, copies=1, **copy_fields):
        e = api.edition(librarian, author=author, title=title, genreId=genre["id"])
        for _ in range(copies):
            api.copy(librarian, e["id"], **copy_fields)
        return e

    kobzar = edition("Тарас Шевченко", "Кобзар", poetry)
    reader, headers = api.reader()
    api.give_back(librarian, api.issue(librarian, reader["id"],
                                       client_copy_id(api, librarian, kobzar))["id"])
    return {
        "reader": reader, "headers": headers,
        "same_author": edition("Тарас Шевченко", "Гайдамаки", prose),
        "same_genre": edition("Леся Українка", "Лісова пісня", poetry),
        "unrelated": edition("Іван Франко", "Захар Беркут", prose),
        "no_copies": edition("Тарас Шевченко", "Наймичка", poetry, copies=0),
    }


def client_copy_id(api, librarian, edition):
    copies = api.client.get(f"/editions/{edition['id']}/copies", headers=librarian).json()
    return copies[0]["id"]


def recommendations(client, shelf):
    r = client.get(f"/readers/{shelf['reader']['id']}/recommendations", headers=shelf["headers"])
    assert r.status_code == 200, r.text
    return {i["edition"]["title"]: i["reason"] for i in r.json()}


# --- REQ-F-032: за авторами
def test_recommends_editions_of_authors_reader_has_read(client, shelf, contract):
    r = client.get(f"/readers/{shelf['reader']['id']}/recommendations", headers=shelf["headers"])

    contract(r, "listReaderRecommendations")
    assert recommendations(client, shelf)["Гайдамаки"] == "same_author"


# --- REQ-F-033: за жанрами
def test_recommends_editions_of_genres_reader_has_read(client, shelf):
    assert recommendations(client, shelf)["Лісова пісня"] == "same_genre"


def test_unrelated_editions_are_not_recommended(client, shelf):
    assert "Захар Беркут" not in recommendations(client, shelf)


# --- REQ-F-034: лише видання, наявні у фонді
def test_edition_without_copies_is_not_recommended(client, shelf):
    assert "Наймичка" not in recommendations(client, shelf)


def test_edition_with_only_written_off_copies_is_not_recommended(client, api, librarian, shelf):
    copy_id = client_copy_id(api, librarian, shelf["same_author"])
    client.post(f"/copies/{copy_id}/write-off", headers=librarian)

    assert "Гайдамаки" not in recommendations(client, shelf)


def test_reader_without_history_gets_no_recommendations(client, api, librarian, shelf):
    reader, headers = api.reader()

    r = client.get(f"/readers/{reader['id']}/recommendations", headers=headers)

    assert r.status_code == 200
    assert r.json() == []


def test_reader_cannot_see_another_readers_recommendations(client, api, shelf):
    _, stranger = api.reader()

    assert client.get(f"/readers/{shelf['reader']['id']}/recommendations", headers=stranger).status_code == 403


# --- REQ-F-052 (адендум, валідація V-6): без уже отриманих видань
def test_returned_edition_is_not_recommended_again(client, shelf):
    # AC-2: «Кобзар» читач уже повернув.
    assert "Кобзар" not in recommendations(client, shelf)


def test_edition_the_reader_currently_holds_is_not_recommended(client, api, librarian, shelf):
    # AC-1: читач зараз тримає «Гайдамаки».
    api.issue(librarian, shelf["reader"]["id"], client_copy_id(api, librarian, shelf["same_author"]))

    assert "Гайдамаки" not in recommendations(client, shelf)


def test_compensated_edition_is_not_recommended(client, api, librarian, clock, shelf):
    # «Будь-яка видача» включає компенсовану (не повернуто, штраф досяг ціни).
    loan = api.issue(librarian, shelf["reader"]["id"], client_copy_id(api, librarian, shelf["same_author"]))
    clock.advance(days=30 + 100)
    assert api.loan(librarian, loan["id"])["status"] == "compensated"

    assert "Гайдамаки" not in recommendations(client, shelf)


def test_unreceived_editions_of_same_author_and_genre_are_still_recommended(client, shelf):
    # AC-3: REQ-F-032 і 033 не послаблено.
    assert recommendations(client, shelf) == {"Гайдамаки": "same_author", "Лісова пісня": "same_genre"}


def test_reader_who_received_everything_related_gets_empty_list(client, api, librarian, shelf):
    # AC-4: порожній список, а не помилка.
    for edition in (shelf["same_author"], shelf["same_genre"]):
        api.issue(librarian, shelf["reader"]["id"], client_copy_id(api, librarian, edition))

    r = client.get(f"/readers/{shelf['reader']['id']}/recommendations", headers=shelf["headers"])

    assert r.status_code == 200
    assert r.json() == []


def test_exclusion_applies_only_to_the_reader_who_received_it(client, api, librarian, shelf):
    # AC-5: інший читач отримав лише «Гайдамаки» (Шевченко) — «Кобзар» йому рекомендується.
    other, other_headers = api.reader()
    loan = api.issue(librarian, other["id"], client_copy_id(api, librarian, shelf["same_author"]))
    api.give_back(librarian, loan["id"])

    r = client.get(f"/readers/{other['id']}/recommendations", headers=other_headers)

    titles = {i["edition"]["title"] for i in r.json()}
    assert "Кобзар" in titles
    assert "Гайдамаки" not in titles
