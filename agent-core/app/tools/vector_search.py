from __future__ import annotations

import logging
from typing import Any, Dict, List

import chromadb

from app.config import settings

logger = logging.getLogger(__name__)

_KNOWLEDGE_BASE = [
    {"id": "kb_001", "doc": "Password reset: Go to the company portal at https://portal.internal/reset. Enter your employee ID and registered email. A reset link will be sent within 2 minutes. If no email received, check spam or contact IT helpdesk at ext. 4357.", "meta": {"category": "account", "severity": "low", "tags": "password,reset,login"}},
    {"id": "kb_002", "doc": "VPN connection issues: Ensure Cisco AnyConnect v5+ is installed. Connect to vpn.company.com with your domain credentials (DOMAIN username). If connection fails, restart the VPN service via Services panel or reboot. Check that firewall is not blocking UDP port 443.", "meta": {"category": "network", "severity": "medium", "tags": "vpn,remote,connection,anyconnect"}},
    {"id": "kb_003", "doc": "Printer not connecting: Navigate to Settings > Printers and Scanners > Add Printer. Select the network printer by its IP address. Install PCL6 drivers from the software portal if prompted. For Mac users, use the HP Easy Install utility from Self Service.", "meta": {"category": "hardware", "severity": "low", "tags": "printer,peripheral,driver"}},
    {"id": "kb_004", "doc": "Email not sending from Outlook: Check SMTP settings: server smtp.company.com, port 587, TLS enabled. Verify your mailbox quota under File > Account Settings. If over quota, archive emails. Restart Outlook and attempt to send again.", "meta": {"category": "software", "severity": "low", "tags": "email,outlook,smtp,quota"}},
    {"id": "kb_005", "doc": "Laptop will not boot: Hold the power button for 10 seconds to force shutdown. Remove all external devices. Boot holding F8 for safe mode on Windows. If BSOD appears, note the error code and call IT. Check battery charge level.", "meta": {"category": "hardware", "severity": "high", "tags": "laptop,boot,bsod,startup"}},
    {"id": "kb_006", "doc": "Slow internet connection: Run a speed test at speedtest.company.com. Restart your router and modem. Check Task Manager for bandwidth usage. Contact network team if wired speed is below 10 Mbps.", "meta": {"category": "network", "severity": "medium", "tags": "internet,slow,bandwidth,network"}},
    {"id": "kb_007", "doc": "Software installation failure: Verify admin rights or submit a software request via the IT portal. Check disk space (minimum 5 GB free). Temporarily disable antivirus during install. Download from the company software portal at software.internal.", "meta": {"category": "software", "severity": "low", "tags": "installation,software,admin,permissions"}},
    {"id": "kb_008", "doc": "Account lockout resolution: Accounts lock after 5 failed login attempts. Wait 30 minutes for automatic unlock, or contact the helpdesk with your employee ID. Reset your password immediately after unlock.", "meta": {"category": "account", "severity": "medium", "tags": "lockout,account,password,active-directory"}},
    {"id": "kb_009", "doc": "Two-factor authentication setup: Download the Microsoft Authenticator app. Navigate to account.company.com/mfa and sign in. Click Set up MFA and scan the QR code. Enter the 6-digit verification code. Save backup codes in a secure location.", "meta": {"category": "security", "severity": "medium", "tags": "mfa,2fa,authenticator,security"}},
    {"id": "kb_010", "doc": "File access denied: Confirm with your manager whether you should have access. Submit an access request via the IT portal with business justification. Permissions are reviewed within 24 hours. For urgent production access, call the IT hotline at ext. 4911.", "meta": {"category": "security", "severity": "medium", "tags": "access,permissions,file,authorization"}},
    {"id": "kb_011", "doc": "Remote desktop connection issues: Ensure RDP is enabled on the target machine via System > Remote Settings. Use the format DOMAIN then username. Port 3389 must be open in Windows Firewall. Connect to VPN first for remote access to internal machines.", "meta": {"category": "network", "severity": "medium", "tags": "rdp,remote,desktop,3389"}},
    {"id": "kb_012", "doc": "Outlook calendar sync problems: Remove and re-add your Exchange account in File > Account Settings. Check calendar sharing permissions. Run the Outlook repair tool via Control Panel > Programs > Office > Repair.", "meta": {"category": "software", "severity": "low", "tags": "outlook,calendar,sync,exchange"}},
    {"id": "kb_013", "doc": "Microsoft Teams video call issues: Update Teams to the latest version via Help > Check for Updates. Check camera and microphone permissions in Windows Settings > Privacy. Test audio and video in Teams Settings > Devices before meetings.", "meta": {"category": "software", "severity": "low", "tags": "teams,video,call,meeting,camera"}},
    {"id": "kb_014", "doc": "Blue screen of death: Photograph the error code. Boot into Safe Mode (F8 at startup). Run sfc /scannow in an elevated command prompt. Check Event Viewer for critical errors. Run Windows Memory Diagnostic (mdsched.exe) if recurring.", "meta": {"category": "hardware", "severity": "critical", "tags": "bsod,crash,memory,kernel,bluescreen"}},
    {"id": "kb_015", "doc": "Hard drive space running low: Use WinDirStat to identify large files. Empty the Recycle Bin and clear browser caches. Move large files to the network share at fileserver/users. Contact IT for an SSD upgrade if under 20 GB free.", "meta": {"category": "hardware", "severity": "low", "tags": "storage,disk,space,cleanup,ssd"}},
    {"id": "kb_016", "doc": "Antivirus alert malware detected: CrowdStrike Falcon will automatically quarantine the threat. Note the threat name and file path. Disconnect from the network. Call IT Security immediately at ext. 4911. Do not restart the machine until IT arrives.", "meta": {"category": "security", "severity": "critical", "tags": "antivirus,malware,security,crowdstrike"}},
    {"id": "kb_017", "doc": "Software license expiry: Log into the company license portal at licenses.company.com. Check your assigned licenses. Submit a renewal request at least 30 days before expiry with your manager approval.", "meta": {"category": "software", "severity": "medium", "tags": "license,software,renewal,adobe,microsoft"}},
    {"id": "kb_018", "doc": "Wi-Fi connectivity issues: Forget the network and reconnect using your domain credentials. Ensure you connect to CORP-WiFi with 802.1X, not GUEST. Update your network adapter driver via Device Manager. Wired Ethernet is preferred for video calls.", "meta": {"category": "network", "severity": "medium", "tags": "wifi,wireless,connectivity,802.1x"}},
    {"id": "kb_019", "doc": "USB device not recognized: Try a different USB port (prefer USB 3.0 blue ports). Update USB drivers via Device Manager. Check if the device appears in Disk Management. Company policy restricts unauthorized USB storage.", "meta": {"category": "hardware", "severity": "low", "tags": "usb,device,peripheral,driver"}},
    {"id": "kb_020", "doc": "Server timeout and connection errors: Check the IT status board at status.company.com for known incidents. Test connectivity with ping and traceroute to the server. Verify proxy settings match IT documentation. Open a P1 incident if production servers are affected.", "meta": {"category": "infrastructure", "severity": "critical", "tags": "server,timeout,connection,p1,incident"}},
]


def get_chroma_client() -> chromadb.HttpClient:
    return chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port)


def seed_knowledge_base() -> None:
    """Seed ChromaDB with 20 IT support knowledge base entries."""
    client = get_chroma_client()
    collection = client.get_or_create_collection(
        name=settings.chroma_collection,
        metadata={"hnsw:space": "cosine"},
    )
    if collection.count() >= 20:
        logger.info("Knowledge base already seeded (%d entries).", collection.count())
        return
    existing_ids = set(collection.get()["ids"])
    new_items = [item for item in _KNOWLEDGE_BASE if item["id"] not in existing_ids]
    if not new_items:
        return
    collection.add(
        documents=[item["doc"] for item in new_items],
        metadatas=[item["meta"] for item in new_items],
        ids=[item["id"] for item in new_items],
    )
    logger.info("Seeded %d knowledge base entries into ChromaDB.", len(new_items))


def search_knowledge_base(query: str, n_results: int = 3) -> List[Dict[str, Any]]:
    """Perform cosine-similarity search against the IT knowledge base."""
    client = get_chroma_client()
    collection = client.get_or_create_collection(
        name=settings.chroma_collection,
        metadata={"hnsw:space": "cosine"},
    )
    count = collection.count()
    if count == 0:
        logger.warning("Knowledge base is empty -- seeding now.")
        seed_knowledge_base()
        count = collection.count()
    actual_n = min(n_results, count)
    results = collection.query(query_texts=[query], n_results=actual_n)
    items: List[Dict[str, Any]] = []
    for i, doc in enumerate(results["documents"][0]):
        items.append({
            "document": doc,
            "distance": results["distances"][0][i],
            "metadata": results["metadatas"][0][i],
            "id": results["ids"][0][i],
        })
    return items
