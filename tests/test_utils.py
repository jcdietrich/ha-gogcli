import pytest
from unittest.mock import MagicMock, patch, ANY
from aioresponses import aioresponses
import tarfile
import io
import os
from custom_components.gogcli.utils import install_binary, GITHUB_RELEASE_URL, _get_system_info

@pytest.mark.asyncio
async def test_install_binary_tar_gz():
    hass = MagicMock()
    hass.config.path.return_value = "/mock/path/custom_components/gogcli/bin/gogcli"
    
    # Create a mock tar.gz content
    file_content = b"fake-binary-content"
    tar_stream = io.BytesIO()
    with tarfile.open(fileobj=tar_stream, mode="w:gz") as tar:
        tarinfo = tarfile.TarInfo(name="gogcli")
        tarinfo.size = len(file_content)
        tar.addfile(tarinfo, io.BytesIO(file_content))
    tar_bytes = tar_stream.getvalue()

    os_name, arch, ext = _get_system_info()
    expected_url = GITHUB_RELEASE_URL.format(version="0.9.0", os=os_name, arch=arch, ext=ext)

    with aioresponses() as m:
        m.get(expected_url, status=200, body=tar_bytes)
        
        with patch("builtins.open", new_callable=MagicMock) as mock_open:
            mock_file = MagicMock()
            mock_open.return_value.__enter__.return_value = mock_file
            
            with patch("os.makedirs") as mock_makedirs, \
                 patch("os.chmod") as mock_chmod, \
                 patch("os.stat") as mock_stat:
                
                path = await install_binary(hass)
                
                assert path == "/mock/path/custom_components/gogcli/bin/gogcli"
                mock_makedirs.assert_called_with("/mock/path/custom_components/gogcli/bin", exist_ok=True)
                mock_file.write.assert_called_with(file_content)
                mock_chmod.assert_called()

@pytest.mark.asyncio
async def test_install_binary_download_fail():
    hass = MagicMock()
    os_name, arch, ext = _get_system_info()
    expected_url = GITHUB_RELEASE_URL.format(version="0.9.0", os=os_name, arch=arch, ext=ext)

    with aioresponses() as m:
        m.get(expected_url, status=404)
        
        with pytest.raises(RuntimeError, match="Failed to download gogcli: 404"):
            await install_binary(hass)
