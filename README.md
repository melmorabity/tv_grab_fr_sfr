# tv_grab_fr_sfr

Grab French television listings from SFR STB EPG sources in XMLTV format.

## Authors

Mohamed El Morabity

## Usage

    tv_grab_fr_sfr.py --help
    tv_grab_fr_sfr.py [--config-file FILE] --configure
    tv_grab_fr_sfr.py [--config-file FILE] [--output FILE] [--days N] [--offset N] [--quiet] [--debug]
	tv_grab_fr_sfr.py --list-channels [--config-file FILE] [--output FILE] [--quiet] [--debug]
    tv_grab_fr_sfr.py --description
    tv_grab_fr_sfr.py --capabilities
    tv_grab_fr_sfr.py --version

## Description

Output TV listings for several channels provided by the French ISP SFR. The data comes from data.stb.neuf.fr.

First run `tv_grab_fr_sfr.py --configure` to choose which channels you want to download. Then running `tv_grab_fr_sfr.py` with no arguments will output listings in XML format to standard output.

    --configure

Ask for each available channel whether to download and write the configuration file.

    --config-file FILE

Set the name of the configuration file, the default is `~/.xmltv/tv_grab_fr_sfr.conf`. This is the file written by `--configure` and read when grabbing.

    --output FILE

Write to `FILE` rather than standard output.

    --days N

Grab `N` days. The default is 1.

    --offset N

Start `N` days in the future. The default is to start from now on (= 0).

    --list-channels

Output a list of all channels that data is available. The list is in XMLTV format.

    --quiet

Only print error messages to standard error.

    --debug

Provide more information on progress to standard error to help in debugging.

    --capabilities

Show which capabilities the grabber supports. For more information, see http://wiki.xmltv.org/index.php/XmltvCapabilities.

    --description

Show the description of the grabber.

    --version

Show the version of the grabber.

    --help

Print a help message and exit.
