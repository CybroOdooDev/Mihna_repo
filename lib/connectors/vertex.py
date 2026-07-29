# Part of Odoo. See LICENSE file for full copyright and licensing details.
from .base import L10nOmEdiConnector, register_connector


@register_connector('vertex')
class VertexConnector(L10nOmEdiConnector):
    """ Stub connector for Vertex.

    Their developer portal confirms OAuth2 with a client_id/client_secret pair, generated after
    creating a Vertex e-Invoicing account, used to obtain an access token.

    NOT CONFIRMED: the exact token endpoint URL and request parameters - the specific "API
    Authentication and Access" documentation page exists but its full content wasn't accessible during
    research; only the surrounding portal pages confirming the client_id/client_secret concept were.
    """
    display_name = "Vertex"
    REQUIRED_CONFIG = ['client_id', 'client_secret']
    CONFIG_STATUS = 'partial'
    CONFIG_SOURCE = "https://developer.vertexinc.com/einvoicing/docs/access-token"
    CONFIG_NOTES = ("Confirmed: OAuth2 with a client_id/client_secret pair. NOT confirmed: exact token "
                     "endpoint/request parameters - the relevant doc page's full content was not "
                     "accessible during research.")
