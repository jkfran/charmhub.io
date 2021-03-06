import math

import flask
import talisker
from canonicalwebteam.discourse import DiscourseAPI, TutorialParser, Tutorials


def init_tutorials(app, url_prefix):
    discourse_index_id = 3393
    category_id = 22

    session = talisker.requests.get_session()
    tutorials_discourse = Tutorials(
        parser=TutorialParser(
            api=DiscourseAPI(
                base_url="https://discourse.charmhub.io/", session=session
            ),
            index_topic_id=discourse_index_id,
            category_id=category_id,
            url_prefix=url_prefix,
        ),
        document_template="tutorials/tutorial.html",
        url_prefix=url_prefix,
        blueprint_name="tutorials",
    )

    @app.route(url_prefix)
    def tutorials():
        page = flask.request.args.get("page", default=1, type=int)
        topic = flask.request.args.get("topic", default=None, type=str)
        sort = flask.request.args.get("sort", default=None, type=str)
        posts_per_page = 15
        tutorials_discourse.parser.parse()
        if not topic:
            metadata = tutorials_discourse.parser.metadata
        else:
            metadata = [
                doc
                for doc in tutorials_discourse.parser.metadata
                if topic in doc["categories"]
            ]

        if sort == "difficulty-desc":
            metadata = sorted(
                metadata, key=lambda k: k["difficulty"], reverse=True
            )

        if sort == "difficulty-asc" or not sort:
            metadata = sorted(
                metadata, key=lambda k: k["difficulty"], reverse=False
            )

        total_pages = math.ceil(len(metadata) / posts_per_page)

        return flask.render_template(
            "tutorials/index.html",
            navigation=tutorials_discourse.parser.navigation,
            forum_url=tutorials_discourse.parser.api.base_url,
            metadata=metadata,
            page=page,
            topic=topic,
            sort=sort,
            posts_per_page=posts_per_page,
            total_pages=total_pages,
        )

    tutorials_discourse.init_app(app)
