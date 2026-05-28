'''Pure keyboard-need predicates for IA wizards (no pygame, unit-testable). GAB-13.'''


def ia_wizard_needs_keyboard(dl_show, dl_step, col_show, col_step, col_adding_custom):
    """True iff an IA wizard is on a text-entry step needing the soft keyboard."""
    if dl_show and dl_step == "url":
        return True
    if col_show and (
        col_step in ("url", "name")
        or (col_step == "formats" and col_adding_custom)
    ):
        return True
    return False
