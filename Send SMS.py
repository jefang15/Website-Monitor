

from password import email, email_password
import asyncio
import re
from email.message import EmailMessage
from typing import Collection, List, Tuple, Union
import aiosmtplib


async def send_txt(
        num: Union[str, int], carrier: str, email2: str, pword: str, msg2: str, subj: str
        ) -> Tuple[dict, str]:
    to_email = CARRIER_MAP[carrier]

    # build message
    message = EmailMessage()
    message["From"] = email2
    message["To"] = f"{num}@{to_email}"
    message["Subject"] = subj
    message.set_content(msg2)

    # send
    send_kws = dict(username=email2, password=pword, hostname=HOST, port=587, start_tls=True)
    res = await aiosmtplib.send(message, **send_kws)  # type: ignore
    msg3 = "failed" if not re.search(r"\sOK\s", res[1]) else "succeeded"
    print(msg3)
    return res


async def send_txts(
        nums: Collection[Union[str, int]], carrier: str, email2: str, pword: str, msg2: str, subj: str
        ) -> List[Tuple[dict, str]]:
    tasks = [send_txt(n, carrier, email2, pword, msg2, subj) for n in set(nums)]
    return await asyncio.gather(*tasks)


HOST = 'smtp.outlook.com'

CARRIER_MAP = {
    "verizon": "vtext.com",
    "tmobile": "tmomail.net",
    "sprint": "messaging.sprintpcs.com",
    "at&t": "txt.att.net",
    "boost": "smsmyboostmobile.com",
    "cricket": "sms.cricketwireless.net",
    "uscellular": "email.uscc.net",
    }

coro = send_txt('2068980303', "verizon", email, email_password, "Dummy msg", "Dummy subj")
# _nums = {"999999999", "000000000"}
# coro = send_txts(_nums, _carrier, _email, _pword, _msg, _subj)

asyncio.run(coro)

# Source: https://github.com/acamso/demos/blob/master/_email/send_txt_msg.py
