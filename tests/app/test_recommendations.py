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
