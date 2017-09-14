import sys


def print_obj(x, fline=""):
    for field in x._meta.get_fields():
        if field.is_relation:
            if not hasattr(field, "get_accessor_name"):
                if getattr(field, 'many_to_many'):
                    m2m_field = getattr(x, field.name)
                    print(f"{fline}{field.name}:")
                    flineind = fline + '\t'
                    for i, ent in enumerate(getattr(m2m_field, "all")(), 1):
                        print(f"{flineind}#{i}: {ent}")
                else:
                    print(
                        f"{fline}{field.name}.ForeignKeyID: "
                        f"{getattr(getattr(x, field.name),'id')}"
                    )

            else:
                accessor = field.get_accessor_name()
                relobj = getattr(x, accessor)
                print(f"{accessor}:")
                for f in relobj.all():
                    print_obj(f, fline + "\t")
        else:
            print(f"{fline}{field.name}: {getattr(x, field.name)}")

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
