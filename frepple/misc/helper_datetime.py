##############################################################################
# Copyright (c) 2021 brain-tec AG (https://bt-group.com)
# All Right Reserved
#
# See LICENSE file for full licensing details.
##############################################################################

from odoo import fields
import pytz
from pytz import utc

def get_utc_date(date_str, tz_for_exporting):
    """ Helper function to return the UTC string for a received date in the timezone specified for frepple """
    received_date = fields.Datetime.to_datetime(date_str.replace('T', ' '))
    return fields.Datetime.to_string(pytz.timezone(tz_for_exporting).localize(received_date).astimezone(utc))
