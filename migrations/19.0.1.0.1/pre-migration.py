import logging

_logger = logging.getLogger(__name__)

def migrate(cr, version):
    _logger.info("Running pre-migration for subscription_management: Dropping obsolete constraints.")
    cr.execute("ALTER TABLE stock_picking DROP COLUMN IF EXISTS subscription_id CASCADE;")
    cr.execute("ALTER TABLE account_move DROP COLUMN IF EXISTS subscription_id CASCADE;")
    cr.execute("ALTER TABLE subscription_usage DROP COLUMN IF EXISTS subscription_id CASCADE;")
    _logger.info("Successfully dropped obsolete subscription_id columns to resolve constraints.")
