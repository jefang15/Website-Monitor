
from password import email, email_password
import asyncio
import re
from email.message import EmailMessage
from typing import Collection, List, Tuple, Union
import aiosmtplib


async def send_txt(num: Union[str, int], carrier: str, email: str, pword: str, msg2: str, subj: str) -> Tuple[dict, str]:

    to_email = CARRIER_MAP[carrier]

    # Build message
    message = EmailMessage()
    message['From'] = email
    message['To'] = f"{num}@{to_email}"
    message['Subject'] = subj
    message.set_content(msg2)

    # Send SMS
    send_kws = dict(username=email, password=pword, hostname=HOST, port=587, start_tls=True)
    res = await aiosmtplib.send(message, **send_kws)  # type: ignore
    msg3 = 'failed' if not re.search(r'\sOK\s', res[1]) else 'SMS Sent'

    print(msg3)

    return res


HOST = 'smtp.outlook.com'

CARRIER_MAP = {
    'verizon': 'vtext.com',
    'tmobile': 'tmomail.net',
    'sprint': 'messaging.sprintpcs.com',
    'at&t': 'txt.att.net',
    'boost': 'smsmyboostmobile.com',
    'cricket': 'sms.cricketwireless.net',
    'uscellular': 'email.uscc.net',
    }

coro = send_txt(
    '2068980303',
    'verizon',
    email,
    email_password,
    'Test',
    'Test Subj')

asyncio.run(coro)

# Source: https://github.com/acamso/demos/blob/master/_email/send_txt_msg.py
