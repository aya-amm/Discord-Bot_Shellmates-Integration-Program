
from bot.sync import compute_changes


def test1():   #normal case

    current = {"Designer"}    
    wanted = {"Developer"}
    managed = {"Developer", "Designer", "HR"}

    to_add, to_remove = compute_changes(
        current, wanted, managed
    )

    assert to_add == {"Developer"}
    assert to_remove == {"Designer"}


def test2(): #case of preserving the unmanaged roles

    current = {"Moderator", "Developer"}
    wanted = {"Developer"}
    managed = {"Developer", "Designer", "HR"}

    to_add, to_remove = compute_changes(
        current, wanted, managed
    )

    assert to_add == set()
    assert to_remove == set()
    assert "Moderator" not in to_remove


def test3():  #case of not adding unmanaged roles

    current = set()
    wanted = {"Administrator"}
    managed = {"Developer", "Designer", "HR"}

    to_add, to_remove = compute_changes(
        current, wanted, managed
    )

    assert to_add == set()
    assert to_remove == set()


def test4(): # case of having no changes

    current = {"Developer"}
    wanted = {"Developer"}
    managed = {"Developer", "Designer", "HR"}

    to_add, to_remove = compute_changes(
        current, wanted, managed
    )

    assert to_add == set()
    assert to_remove == set()


