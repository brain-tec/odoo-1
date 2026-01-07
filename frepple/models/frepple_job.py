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

from datetime import datetime, timedelta
import gzip
import json
import logging
from odoo import fields, models, api, release
import os
from pathlib import Path
import requests
import secrets
from tempfile import NamedTemporaryFile
import time
from werkzeug.security import check_password_hash, generate_password_hash

from ..controllers.frepplexml import encode_jwt
from ..controllers.outbound import exporter, Odoo_generator

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

    def action_start(self):
        for rec in self:
            rec.status = "started"
            rec.started = fields.Datetime.now()

    @api.model
    def action_cancel_all(self, company_id):
        jobs_to_cancel = self.env["frepple.job"].search(
            [
                ("company_id.id", "=", company_id),
                ("finished", "=", False),
                ("status", "=", "Waiting for results"),
            ]
        )
        jobs_to_cancel.write({"status": "cancelled"})

    @api.model
    def action_launch(self, company_id):
        filename = None
        try:
            # Create a job and its token
            token = secrets.token_urlsafe(64)
            job = self.create(
                {
                    "status": "created",
                    "started": datetime.now(),
                    "user_id": self.env.user.id,
                    "hashed_token": generate_password_hash(token),
                    "company_id": company_id,
                }
            )

            job.write({"status": "Collecting data"})

            company = self.env["res.company"].browse(company_id)
            if not company.exists():
                raise ValueError(f"Company with id {company_id} does not exist.")

            xp = exporter(
                Odoo_generator(self.env),
                None,
                uid=self.env.user.id,
                database=None,
                company=company.name,
                mode=1,
                timezone=None,
                singlecompany=True,
                delta=0,
                language=self.env.context.get("lang", "en_US"),
                apps="",
            )

            # last empty double quote is to let python understand frepple is a folder.
            xml_folder = os.path.join(str(Path.home()), "logs", "frepple", "")
            os.makedirs(os.path.dirname(xml_folder), exist_ok=True)

            tmpfile = NamedTemporaryFile(mode="w+t", delete=False, dir=xml_folder)
            filename = tmpfile.name
            tmpfile.close()

            # Generate a file with all data
            with gzip.open(filename, "wb") as tmpfile:
                for i in xp.run():
                    tmpfile.write(i.encode("utf-8"))

            # Submitting the file to frepple
            job.write({"status": "Submitting data"})
            with open(filename, "rb") as f:

                metadata = {
                    "email": self.env.user.email,
                    "odoo_url": self.env["ir.config_parameter"]
                    .sudo()
                    .get_param("web.base.url"),
                    "company": company.name,
                    "version": release.version,
                    "submitted": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "token": token,
                    "database": self.env.cr.dbname,
                }

                webtoken = encode_jwt(
                    {"exp": round(time.time()) + 600, "user": self.env.user.login},
                    company.webtoken_key,
                )
                if not isinstance(webtoken, str):
                    webtoken = webtoken.decode("ascii")

                response = requests.post(
                    f"{company.frepple_server.replace("localhost", "host.docker.internal")}/odoo/submit/",
                    headers={"Authorization": f"Bearer {str(webtoken)}"},
                    files={
                        "datafile": ("odoo_data.json", f, "application/octet-stream"),
                        "metadata": (
                            "metadata.json",
                            json.dumps(metadata),
                            "application/json",
                        ),
                    },
                    timeout=300,
                )
                if response.status_code != 200:
                    job.write({"status": f"Failure submitting: {response.content}"})
                    logger.critical("Job submission failed.")
                else:
                    job.write({"status": "Waiting for results"})
        finally:
            if filename:
                os.remove(filename)
