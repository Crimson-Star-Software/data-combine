import sys


def updt(total, progress):
    """
    Displays or updates a console progress bar.

    Original source: https://stackoverflow.com/a/15860757/1391441
    This version is from stack overflow user Gabriel:
        https://stackoverflow.com/users/1391441/gabriel
    """
    barLength, status = 20, ""
    progress = float(progress) / float(total)
    if progress >= 1.:
        progress, status = 1, "\r\n"
    block = int(round(barLength * progress))
    text = "\r[{}] {:.2f}% {}".format(
        "#" * block + "-" * (barLength - block), round(progress * 100, 2),
        status)
    sys.stdout.write(text)
    sys.stdout.flush()
