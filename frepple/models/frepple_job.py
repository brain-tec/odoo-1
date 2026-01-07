# -*- coding: utf-8 -*-
#
# Copyright (C) 2025 by frePPLe bv
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

from odoo import fields, models, api
import secrets
import logging
from datetime import datetime, timedelta
from werkzeug.security import check_password_hash, generate_password_hash

logger = logging.getLogger(__name__)


class FreppleJob(models.Model):
    _name = "frepple.job"
    _description = "Frepple Jobs"

    company_id = fields.Many2one(
        "res.company", string="Company", default=lambda self: self.env.company
    )
    status = fields.Char("status")
    user_id = fields.Many2one(
        "res.users", string="Submitted by", default=lambda self: self.env.user
    )
    started = fields.Datetime(string="Date when the job was launched")
    finished = fields.Datetime(string="Date when a response was received from frePPLe")
    hashed_token = fields.Char(
        string="Hashed secret token", groups="base.group_system", required=True
    )

    @api.model
    def createJob(self, company_id):
        token = secrets.token_urlsafe(64)
        j = self.env["frepple.job"].create(
            {
                "status": "created",
                "started": datetime.now(),
                "user_id": self.env.user.id,
                "hashed_token": generate_password_hash(token),
                "company_id": company_id,
            }
        )
        self.env.cr.commit()
        return j, token

    @api.model
    def findJob(self, token):
        for j in self.env["frepple.job"].search(
            [
                ("finished", "=", False),
                ("status", "=", "Waiting for results"),
                (
                    "started",
                    ">",
                    (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S"),
                ),
            ],
            order="started asc",
        ):
            if check_password_hash(j.hashed_token, token):
                return j
        return None

    def action_cancel(self):
        for rec in self:
            rec.status = "cancelled"

    @api.model
    def action_cancel_all(self, company_id):
        for j in self.env["frepple.job"].search(
            [
                ("company_id.id", "=", company_id),
                ("finished", "=", False),
                ("status", "=", "Waiting for results"),
            ]):
            j.status = "cancelled"

    def action_start(self):
        for rec in self:
            rec.status = "started"
            rec.started = fields.Datetime.now()
