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


def test_percent_value_written_verbatim():
    # interpolation=None is required so 86Box values containing % are not
    # mis-parsed as configparser interpolation markers.
    text = "[Hard disks]\nhdd_01_fn = old.img\n"
    value = r"C:\WINDOWS\%USERNAME%\hdd.img"
    out = set_values(text, {("Hard disks", "hdd_01_fn"): value})
    # Must not raise configparser.InterpolationSyntaxError and must round-trip.
    assert value in out
