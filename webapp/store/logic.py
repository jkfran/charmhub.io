import sys
import datetime
from collections import OrderedDict

import humanize
from dateutil import parser
from docstring_extractor import get_docstrings
from webapp.helpers import decrease_headers
from webapp.helpers import (
    discourse_api,
    format_slug,
    get_yaml_loader,
    md_parser,
)

yaml = get_yaml_loader()
UBUNTU_SERIES = {
    "warty": "4.10",
    "hoary": "5.04",
    "breezy": "5.10",
    "dapper": "6.06 LTS",
    "edgy": "6.10",
    "feisty": "7.04",
    "gutsy": "7.10",
    "hardy": "8.04 LTS",
    "intrepid": "8.10",
    "jaunty": "9.04",
    "karmic": "9.10",
    "lucid": "10.04 LTS",
    "maverick": "10.10",
    "natty": "11.04",
    "oneiric": "11.10",
    "precise": "12.04 LTS",
    "quantal": "12.10",
    "raring": "13.04",
    "saucy": "13.10",
    "trusty": "14.04 LTS",
    "utopic": "14.10",
    "vivid": "15.04",
    "wily": "15.10",
    "xenial": "16.04 LTS",
    "yakkety": "16.10",
    "zesty": "17.04",
    "artful": "17.10",
    "bionic": "18.04 LTS",
    "cosmic": "18.10",
    "disco": "19.04",
    "eoan": "19.10",
    "focal": "20.04 LTS",
    "groovy": "20.10",
}

CATEGORIES = {
    "ai_ml": "ai/ml",
    "ai": "ai/ml",
    "machine_learning": "ai/ml",
    "fortran": "logging-and-tracing",
    "ldap": "logging-and-tracing",
    "nginx": "logging-and-tracing",
    "telemetry": "logging-and-tracing",
    "system": "logging-and-tracing",
    "lsf_server": "logging-and-tracing",
    "ops": "monitoring",
    "monitoring": "monitoring",
    "reporting": "monitoring",
    "cpu": "monitoring",
    "deploy": "monitoring",
    "prometheus": "monitoring",
    "workload_management": "monitoring",
    "ops, monitoring": "monitoring",
    "job_scheduler": "monitoring",
    "network": "networking",
    "content_cache": "networking",
    "networking": "networking",
    "dns": "networking",
    "cache_proxy": "networking",
    "reverse_proxy": "networking",
    "big_data": "big-data",
    "bigdata": "big-data",
    "tensorflow": "big-data",
    "hadoop": "big-data",
    "ampq": "big-data",
    "analytics": "big-data",
    "social": "big-data",
    "kubernetes": "containers",
    "controllers": "containers",
    "kubeflow": "containers",
    "containers": "containers",
    "authentication": "security",
    "identity": "security",
    "security": "security",
    "app-servers": "storage",
    "web-server": "storage",
    "file-servers": "storage",
    "storage": "storage",
    "ftp": "storage",
    "file-server": "storage",
    "capacity-planning": "storage",
    "openstack": "cloud",
    "infrastructure": "cloud",
    "keystore": "cloud",
    "databases": "database",
    "database": "database",
}

PLATFORMS = {
    "ubuntu": "linux",
    "centos": "linux",
}


def get_banner_url(media):
    """
    Get banner url from media object

    :param media: the media dictionnary
    :returns: the banner url
    """
    for m in media:
        if m["type"] == "banner":
            return m["url"]

    return None


def get_channel_map(channel_map):
    """
    Reformat channel map to return a channel map
    with unique risk

    :param channel_map: the channel map from the api
    :returns: the channel map reformatted
    """
    new_map = []
    for channel in channel_map:
        for res in new_map:
            if channel["channel"]["name"] == res["channel"]["name"]:
                break
        else:
            new_map.append(channel)

    return new_map


def convert_channel_maps(channel_map):
    """
    Converts channel maps list to format easier to manipulate

    :param channel_maps: The channel maps list returned by the API

    :returns: The channel maps reshaped
    """
    result = {}
    track_order = {"latest": 1}
    risk_order = {"stable": 1, "candidate": 2, "beta": 3, "edge": 4}

    for channel in channel_map:
        track = channel["channel"].get("track", "latest")
        risk = channel["channel"]["risk"]

        if track not in result:
            result[track] = {}

        if risk not in result[track]:
            result[track][risk] = []

        info = {
            "released_at": convert_date(channel["channel"]["released-at"]),
            "version": channel["revision"]["version"],
            "channel": channel["channel"]["name"],
            "risk": channel["channel"]["risk"],
            "size": channel["revision"]["download"]["size"],
            "platforms": convert_series_to_ubuntu_versions(
                extract_series(channel)
            ),
            "architecture": channel["channel"]["platform"]["architecture"],
            "revision": channel["revision"],
        }

        result[track][risk].append(info)

    # Order tracks and risks
    result = OrderedDict(
        sorted(
            result.items(), key=lambda x: track_order.get(x[0], sys.maxsize)
        )
    )

    for track, track_data in result.items():
        result[track] = OrderedDict(
            sorted(
                track_data.items(),
                key=lambda x: risk_order.get(x[0], sys.maxsize),
            )
        )

    return result


def extract_resources(channel):
    """
    Extract resources from channel map

    :param channel_maps: The channel maps list returned by the API

    :returns: Charm resource names
    """
    resources = []

    channel_resources = channel["resources"]

    for resource in channel_resources:
        resources.append(
            {"name": resource["name"], "revision": resource["revision"]}
        )

    return resources


def extract_series(channel):
    """
    Extract ubuntu series from channel map

    :param channel_maps: The channel maps list returned by the API

    :returns: Ubuntu series
    """
    series = []

    for platform in channel["revision"]["platforms"]:
        series.append(platform["series"])

    return series


def convert_series_to_ubuntu_versions(series):
    """Return Ubuntu version based on code name series

    Args:
        series (str|list): Ubuntu series

    Returns:
        str|list: Ubuntu version
    """
    if isinstance(series, str):
        return UBUNTU_SERIES.get(series, series.capitalize())
    elif isinstance(series, list):
        result = []
        for s in series:
            result.append(convert_series_to_ubuntu_versions(s))
    else:
        raise TypeError("Invalid series object")

    # Order from greater to lower version
    return sorted(result, reverse=True)


def convert_date(date_to_convert):
    """
    Convert date to human readable format: Month Day Year

    If date is less than a day return: today or yesterday

    Format of date to convert: 2019-01-12T16:48:41.821037+00:00
    Output: Jan 12 2019

    :param date_to_convert: Date to convert
    :returns: Readable date
    """
    date_parsed = parser.parse(date_to_convert).replace(tzinfo=None)
    delta = datetime.datetime.now() - datetime.timedelta(days=1)
    if delta < date_parsed:
        return humanize.naturalday(date_parsed).title()
    else:
        return date_parsed.strftime("%-d %B %Y")


def get_icons(package):
    media = package["result"]["media"]
    return [m["url"] for m in media if m["type"] == "icon"]


def get_categories(categories_json):
    """Retrieve and flatten the nested array from the legacy API response.
    :param categories_json: The returned json
    :returns: A list of categories
    """

    categories = []
    i = 0

    for category in categories_json:
        mapped_catgory = CATEGORIES.get(category["name"], "other")
        # This is a hack to show only one category that is different
        # than other if it exists. Otherwise show other.
        if i < len(categories_json) - 1:
            if not mapped_catgory == "other":
                categories.append(
                    {
                        "slug": mapped_catgory,
                        "name": format_slug(mapped_catgory),
                    }
                )
                return categories
        else:
            categories.append(
                {
                    "slug": mapped_catgory,
                    "name": format_slug(mapped_catgory),
                }
            )
            return categories
        i = i + 1


def get_docs_topic_id(metadata_yaml):
    """
    Return discourse topic ID or None
    """
    base_url = discourse_api.base_url
    # TODO this is a temporary fix (the only charm is mattermost)
    old_url = "https://discourse.juju.is"
    docs_link = metadata_yaml.get("docs")

    if docs_link:
        if docs_link.startswith(base_url):
            topic_id = docs_link[len(base_url) :].split("/")[3]
        elif docs_link.startswith(old_url):
            topic_id = docs_link[len(old_url) :].split("/")[3]
        else:
            return None

        if topic_id.isnumeric():
            return topic_id

    return None


def add_store_front_data(package, details=False):
    extra = {}

    extra["icons"] = get_icons(package)
    extra["os"] = get_os_from_platform(
        package["default-release"]["revision"]["platforms"]
    )
    extra["categories"] = get_categories(package["result"]["categories"])

    if details:
        extra["metadata"] = yaml.load(
            package["default-release"]["revision"]["metadata-yaml"]
        )
        extra["config"] = yaml.load(
            package["default-release"]["revision"]["config-yaml"]
        )
        extra["actions"] = yaml.load(
            package["default-release"]["revision"]["actions-yaml"]
        )

        # Reshape channel maps
        extra["channel_map"] = convert_channel_maps(package["channel-map"])
        extra["resources"] = extract_resources(package["default-release"])

        # Extract all supported series
        extra["series"] = extract_series(package["default-release"])

        # Some needed fields
        extra["publisher_name"] = package["result"]["publisher"][
            "display-name"
        ]
        if "summary" in package["result"]:
            extra["summary"] = package["result"]["summary"]
        extra["platforms"] = convert_series_to_ubuntu_versions(extra["series"])

        # Get charm docs
        extra["docs_topic"] = get_docs_topic_id(extra["metadata"])

    package["store_front"] = extra
    return package


def process_python_docs(library, module_name):
    """Process libraries response from the API
    to generate the HTML output"""

    # Obtain Python docstrings
    docstrings = get_docstrings(library["content"], module_name)

    docstrings["html"] = decrease_headers(
        md_parser(docstrings["docstring"]), 3
    )

    # We support markdown inside docstrings (2 levels)
    for py_part in docstrings["content"]:
        py_part["html"] = decrease_headers(md_parser(py_part["docstring"]), 3)

        for py_part_2 in py_part["content"]:
            py_part_2["html"] = decrease_headers(
                md_parser(py_part_2["docstring"]), 3
            )

    return docstrings


def process_libraries(libraries):
    """Process the libraries response from the API"""

    result = {}

    for lib in libraries["libraries"]:
        lib_parts = lib["library-name"].split(".")

        if len(lib_parts) > 2:
            group_name = ".".join(lib_parts[:-2])
            lib_name = "." + ".".join(lib_parts[-2:])
        else:
            group_name = "others"
            lib_name = lib["library-name"]

        data = {
            "id": lib["library-id"],
            "name": lib_name,
            "hash": lib["hash"],
            "created_at": lib["created-at"],
        }

        if group_name in result:
            result[group_name].append(data)
        else:
            result[group_name] = [data]

    return result


def get_os_from_platform(platforms):
    """
    Get simplified platforms

    ["linux", "windows", "kubernetes"]

    :param platforms: get list of platforms
    :returns: a list of platforms simplified
    """
    os = set()

    for platform in platforms:
        os.add(PLATFORMS.get(platform["os"], platform["os"]))

    return list(os)


def filter_charm(charm, categories=["all"], platform="all"):
    """
    This filter will be done in the API soon.
    :returns: boolean
    """
    # When all is present there is no need to filter
    if categories and "all" not in categories:
        charm_categories = [
            cat["slug"] for cat in charm["store_front"]["categories"]
        ]

        if not any(x in categories for x in charm_categories):
            return False

    # Filter platforms
    if platform != "all" and platform not in charm["store_front"]["os"]:
        return False

    return True
