import os
import shutil

modulename = "PolyQuilt_Fork"
package_folder = os.getcwd() + "/Addons/PolyQuilt_Fork"
filename = os.path.dirname(os.getcwd()) + "/" + modulename

for root, dirs, files in os.walk(package_folder):
    if '__pycache__' in dirs:
        shutil.rmtree(os.path.join(root, '__pycache__'))
        
shutil.make_archive( filename , 'zip', root_dir= package_folder )

print("Package created: " + filename + ".zip")