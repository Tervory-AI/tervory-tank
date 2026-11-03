"""Command conversation storage and worker corridor, local to this Tank box.

Identity headers are assertions from the authenticated Workspace server, never
from a browser. Worker credentials have a separate, narrowly scoped dependency.
The existing router remains the only model-call path.
"""
from __future__ import annotations

import asyncio
import hmac
import json
import logging
import os
import re
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

import command_repo
from trigger_bot_contract import TOOLS as BOT_TOOLS
from base_lists import FindArgs, SaveArgs, ListArgs, SendArgs
from base_audit_commands import StartArgs as AuditStartArgs, CsvArgs as AuditCsvArgs, ReviewArgs as AuditReviewArgs
from tenant_db import tenant_path
from command_stream import AnswerText, TokenSink

router = APIRouter(prefix="/v1/command", tags=["command"])
logger = logging.getLogger(__name__)
_background: set[asyncio.Task] = set()
SQUADS = frozenset({"base", "tiger", "market_lab", "rig", "tisan", "radix", "zenas"})
from trigger_marketing_contract import TOOLS as MARKETING_TOOLS

TOOLS = {
    "trigger": ["trigger.revise", "trigger.voice.learn", "trigger.write.batch", "trigger.scorecard", "trigger.write", "trigger.check", "trigger.voice.show", "trigger.voice.set", "trigger.voice.rollback", "trigger.feedback"],
    "base": ["base.batch", "base.search", "base.find", "base.list.save", "base.lists", "base.list.show", "base.list.export", "base.list.to_crm"],
    "tiger": ["tiger.watch", "tiger.read", "tiger.match", "tiger.match.confirm", "tiger.match.reject", "tiger.position"],
    "market_lab": ["market_lab.research", "market_lab.warnings", "market_lab.predictions", "market_lab.calibration", "market_lab.feeds", "market_lab.alerts.email", "market_lab.alerts.webhook", "market_lab.alerts.off"],
