import click
from unquietcode.tools.markt import render_markdown


@click.group('python3 -m playbook')
def entrypoint():
    """
    playbook-py module command line helper
    """
    pass


@entrypoint.command()
@click.argument('title', metavar='title', type=click.STRING, required=True)
def new(title):
    """
    create a new playbook file
    """
    
    filename = create_new_playbook(title)
    print(f"\ncreated new playbook '{filename}'\n")



@entrypoint.command()
@click.argument('filename', metavar='filename', type=click.STRING, required=True)
def show(filename):
    """
    render the contents of a log file in the terminal
    """
    with open(filename) as file_:
        text = file_.read()
    
    rendered = render_markdown(text)
    print(rendered)
    

# module entrypoint
entrypoint(prog_name='python3 -m playbook')