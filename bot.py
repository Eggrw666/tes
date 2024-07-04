# -*- coding: utf-8 -*-
# @Author   :Solana0x
# @File     :main.py
# @Software :PyCharm
import asyncio
import random
import ssl
import json
import time
import uuid
from loguru import logger
from websockets_proxy import Proxy, proxy_connect
import requests

async def connect_to_wss(socks5_proxy, user_id):
    device_id = str(uuid.uuid3(uuid.NAMESPACE_DNS, socks5_proxy))
    logger.info(device_id)
    while True:
        try:
            await asyncio.sleep(random.uniform(0.1, 1.0))  # Reduced frequency
            custom_headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
            }
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            uri = "wss://proxy.wynd.network:4444/"
            server_hostname = "proxy.wynd.network"
            proxy = Proxy.from_url(socks5_proxy)
            async with proxy_connect(uri, proxy=proxy, ssl=ssl_context, extra_headers={
                "Origin": "chrome-extension://lkbnfiajjmbhnfledhphioinpickokdi",
                "User-Agent": custom_headers["User-Agent"]
            }) as websocket:
                async def send_ping():
                    while True:
                        send_message = json.dumps(
                            {"id": str(uuid.uuid4()), "version": "1.0.0", "action": "PING", "data": {}})
                        logger.debug(send_message)
                        await websocket.send(send_message)
                        await asyncio.sleep(60)  # Increased interval to reduce bandwidth usage

                send_ping_task = asyncio.create_task(send_ping())
                try:
                    while True:
                        response = await websocket.recv()
                        message = json.loads(response)
                        logger.info(message)
                        if message.get("action") == "AUTH":
                            auth_response = {
                                "id": message["id"],
                                "origin_action": "AUTH",
                                "result": {
                                    "browser_id": device_id,
                                    "user_id": user_id,
                                    "user_agent": custom_headers['User-Agent'],
                                    "timestamp": int(time.time()),
                                    "device_type": "extension",
                                    "version": "4.20.2",
                                    "extension_id": "lkbnfiajjmbhnfledhphioinpickokdi"
                                }
                            }
                            logger.debug(auth_response)
                            await websocket.send(json.dumps(auth_response))

                        elif message.get("action") == "PONG":
                            pong_response = {"id": message["id"], "origin_action": "PONG"}
                            logger.debug(pong_response)
                            await websocket.send(json.dumps(pong_response))
                finally:
                    send_ping_task.cancel()

        except Exception as e:
            logger.error(f"Error with proxy {socks5_proxy}: {str(e)}")
            if any(error_msg in str(e) for error_msg in ["[SSL: WRONG_VERSION_NUMBER]", "invalid length of packed IP address string", "Empty connect reply", "Device creation limit exceeded", "sent 1011 (internal error) keepalive ping timeout; no close frame received"]):
                logger.info(f"Removing error proxy from the list: {socks5_proxy}")
                return None  # Signal to the main loop to replace this proxy
            else:
                continue  # Continue to try to reconnect or handle other errors

async def fetch_proxies(socks4_url, socks5_url):
    socks4_proxies = requests.get(socks4_url).text.splitlines()
    socks5_proxies = requests.get(socks5_url).text.splitlines()

    socks4_proxies = [f'socks4://{proxy}' for proxy in socks4_proxies]
    socks5_proxies = [f'socks5://{proxy}' for proxy in socks5_proxies]

    return socks4_proxies + socks5_proxies

async def main():
    _user_id = 'cbad9f0d-7161-42a4-bddd-5274e84c4048'   # Replace Your User ID HERE 
    socks4_url = 'http://list.didsoft.com/get?email=rhdx37@gmail.com&pass=u2pzns&pid=socks4100&showcountry=no&version=socks4'
    socks5_url = 'http://list.didsoft.com/get?email=rhdx37@gmail.com&pass=u2pzns&pid=socks4100&showcountry=no&version=socks5'

    all_proxies = await fetch_proxies(socks4_url, socks5_url)
    active_proxies = random.sample(all_proxies, 100)  # Number of proxies to use
    tasks = {asyncio.create_task(connect_to_wss(proxy, _user_id)): proxy for proxy in active_proxies}

    while True:
        done, pending = await asyncio.wait(tasks.keys(), return_when=asyncio.FIRST_COMPLETED, timeout=3600)
        
        for task in done:
            if task.result() is None:
                failed_proxy = tasks[task]
                logger.info(f"Removing and replacing failed proxy: {failed_proxy}")
                active_proxies.remove(failed_proxy)
                new_proxy = random.choice(all_proxies)
                active_proxies.append(new_proxy)
                new_task = asyncio.create_task(connect_to_wss(new_proxy, _user_id))
                tasks[new_task] = new_proxy  # Replace the task in the dictionary
            tasks.pop(task)  # Remove the completed task whether it succeeded or failed
        
        # Replenish the tasks if any have completed
        for proxy in set(active_proxies) - set(tasks.values()):
            new_task = asyncio.create_task(connect_to_wss(proxy, _user_id))
            tasks[new_task] = proxy

        # Update proxies every 10 minutes
        if done:
            all_proxies = await fetch_proxies(socks4_url, socks5_url)
            active_proxies.extend(random.sample(all_proxies, 100 - len(active_proxies)))

if __name__ == '__main__':
    asyncio.run(main())