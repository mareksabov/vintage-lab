from vintage.cfg import set_values


def test_sets_existing_key_in_existing_section():
    text = "[Floppy and CD-ROM drives]\nfdd_01_image_path = old.img\n"
    out = set_values(text, {("Floppy and CD-ROM drives", "fdd_01_image_path"): "/a/new.img"})
    assert "fdd_01_image_path = /a/new.img" in out
    assert "old.img" not in out


def test_creates_missing_section():
    out = set_values("[General]\nvid = 1\n", {("Hard disks", "hdd_01_fn"): "hdd.img"})
    assert "[Hard disks]" in out
    assert "hdd_01_fn = hdd.img" in out


def test_preserves_other_keys_and_key_case():
    text = "[General]\nWindowedMode = 1\nvid_resize = 0\n"
    out = set_values(text, {("General", "vid_resize"): "1"})
    assert "WindowedMode = 1" in out       # untouched, case preserved
    assert "vid_resize = 1" in out
