from pathlib import Path
import tempfile
import shutil

tmp = Path(tempfile.mkdtemp())
try:
    ws = tmp / 'workspace'
    ws.mkdir()
    
    # Create site-packages like the test does
    pkg = ws / 'site-packages' / 'sharedpkg'
    pkg.mkdir(parents=True)
    (pkg / '__init__.py').write_text('VALUE = "clean"\n')
    
    print(f'Created: {pkg}')
    print(f'site-packages exists: {(ws / "site-packages").exists()}')
    print(f'Files in site-packages: {list((ws / "site-packages").rglob("*"))}')
    
    # Create session workspace
    session_ws = ws / 'session1'
    session_ws.mkdir()
    
    # Copy using the same logic as copy_vendor_packages
    src = ws / 'site-packages'
    dst = session_ws / 'site-packages'
    
    print(f'\nCopying from {src} to {dst}')
    shutil.copytree(src, dst)
    
    print(f'Copied to: {dst}')
    print(f'Exists: {dst.exists()}')
    print(f'Files in copied: {list(dst.rglob("*"))}')
    
finally:
    shutil.rmtree(tmp)
    print('\nTest passed!')
