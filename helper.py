import os
import torch
from torchvision import datasets
import torchvision.transforms as transforms
from torchnet.logger import VisdomPlotLogger
import cv2
from scipy import ndimage
import numpy as np
from scipy.ndimage.morphology import distance_transform_edt as euc_dist

##############
# Eden Dolev #
##############


# Load dataset. For datasets not included with torch `dataset_name` must match directory name
# For each image we resize, convert to torch tensor and normalize. Some also get cropped before
def load_dataset(dataset_name, image_size, batch_size):
    path = 'data/' + dataset_name
    normal_mean = (0.5, 0.5, 0.5)
    normal_std = (0.5, 0.5, 0.5)
    os.makedirs(path, exist_ok=True)
    if dataset_name == 'mnist':
        dataloader = torch.utils.data.DataLoader(
            datasets.MNIST(path, train=True, download=True,
                           transform=transforms.Compose([
                               transforms.Resize(image_size),
                               transforms.ToTensor(),
                               transforms.Normalize(normal_mean, normal_std)
                           ])),
            batch_size=batch_size, shuffle=True)
    elif dataset_name == 'celeba':
        dataloader = torch.utils.data.DataLoader(
            datasets.ImageFolder(path,
                                 transform=transforms.Compose([
                                     transforms.CenterCrop(128),
                                     transforms.Resize(image_size),
                                     transforms.ToTensor(),
                                     transforms.Normalize(normal_mean, normal_std)
                                 ])),
            batch_size=batch_size, shuffle=True)
    elif dataset_name == 'celeba_random_crop':
        dataloader = torch.utils.data.DataLoader(
            datasets.ImageFolder('data/celeba',
                                 transform=transforms.Compose([
                                     transforms.RandomCrop(150),
                                     transforms.Resize(image_size),
                                     transforms.ToTensor(),
                                     transforms.Normalize(normal_mean, normal_std)
                                 ])),
            batch_size=batch_size, shuffle=True)
    elif dataset_name == 'celeba_test':
        dataloader = torch.utils.data.DataLoader(
            datasets.ImageFolder(path,
                                 transform=transforms.Compose([
                                     transforms.CenterCrop(128),
                                     transforms.Resize(image_size),
                                     transforms.ToTensor(),
                                     transforms.Normalize(normal_mean, normal_std)
                                 ])),
            batch_size=batch_size, shuffle=True)
    elif dataset_name == 'lfw':
        dataloader = torch.utils.data.DataLoader(
            datasets.ImageFolder(path,
                                 transform=transforms.Compose([
                                     transforms.CenterCrop(128),
                                     transforms.Resize(image_size),
                                     transforms.ToTensor(),
                                     transforms.Normalize(normal_mean, normal_std)
                                 ])),
            batch_size=batch_size, shuffle=True)
    elif dataset_name == 'custom':
        dataloader = torch.utils.data.DataLoader(
            datasets.ImageFolder(path,
                                 transform=transforms.Compose([
                                     transforms.Resize(image_size),
                                     transforms.CenterCrop(image_size),
                                     transforms.ToTensor(),
                                     transforms.Normalize(normal_mean, normal_std)
                                 ])),
            batch_size=batch_size, shuffle=True)
    elif dataset_name == 'lsun_tower_train':
        dataloader = torch.utils.data.DataLoader(
            datasets.LSUN(path, classes=['tower_train'],
                                 transform=transforms.Compose([
                                     transforms.Resize(image_size),
                                     transforms.CenterCrop(image_size),
                                     transforms.ToTensor(),
                                     transforms.Normalize(normal_mean, normal_std)
                                 ])),
            batch_size=batch_size, shuffle=True)
    elif dataset_name == 'lsun_tower_test':
        dataloader = torch.utils.data.DataLoader(
            datasets.LSUN(path, classes=['tower_test'],
                                 transform=transforms.Compose([
                                     transforms.Resize(image_size),
                                     transforms.CenterCrop(image_size),
                                     transforms.ToTensor(),
                                     transforms.Normalize(normal_mean, normal_std)
                                 ])),
            batch_size=batch_size, shuffle=True)

    return dataloader


# Create Visdom logger
def get_logger(port, name):
    return VisdomPlotLogger('line', port=port, opts={'title': '%s' % name})


# Alpha blend image with a fill image
# `fill` expected to have color where `img` doesn't, and vice versa
def alpha_blend_img(img, fill, Tensor):
    # convert images to np arrays with 0-255 values
    img = to_np(img)
    fill = to_np(fill)

    bin_img = binary_mask(img)
    bin_fill = binary_mask(fill)
    # euclidean distances
    edt1 = euc_dist(bin_img)
    edt2 = euc_dist(bin_fill)

    coords = np.argwhere(fill)
    x_min, y_min, _ = coords.min(axis=0)
    x_max, y_max, _ = coords.max(axis=0)

    blended = np.array(img)

    for i in range(x_min, x_max):
        for j in range(y_min, y_max):
            w1 = edt1[i][j]
            w2 = edt2[i][j]
            if w1 + w2 == 0:
                blended[i][j] = np.array([0, 0, 0])
            else:
                # apply alpha blending to pixels using euclidean distances as weights
                blended[i][j][0] = np.uint8((w1 * img[i][j][0] + w2 * fill[i][j][0]) / (w1 + w2))
                blended[i][j][1] = np.uint8((w1 * img[i][j][1] + w2 * fill[i][j][1]) / (w1 + w2))
                blended[i][j][2] = np.uint8((w1 * img[i][j][2] + w2 * fill[i][j][2]) / (w1 + w2))

    if Tensor is not None:
        # convert back to torch tensors
        blended = np.einsum('ijk->kij', blended)
        blended = Tensor(blended)

    return blended


# Apply alpha blend to batch
def blend_batch(masked_imgs, generated_fills, Tensor=None):
    ret = [alpha_blend_img(img, fill, Tensor) for (img, fill) in zip(masked_imgs, generated_fills)]
    if Tensor is not None:
        ret = torch.stack(ret)
    return ret


# Create binary mask for image
def binary_mask(img):
    sum_channels_img = np.sum(img, axis=2)
    binary_mask = (sum_channels_img > 0) * 1

    return binary_mask


# Poisson blend image with fill (unused)
def poisson_blend_img(img, fill):
    img = img.astype('uint8')
    fill = fill.astype('uint8')

    img = np.einsum('kij->ijk', img)
    fill = np.einsum('kij->ijk', fill)

    cropped_fill = crop_roi(fill)
    bin_fill = ((fill > 0).any(axis=2) * 255).astype('uint8')
    (com_x, com_y) = ndimage.measurements.center_of_mass(bin_fill)
    com = (int(com_x), int(com_y))
    mask = np.ones_like(cropped_fill) * 255

    cv2.imwrite("blended_test/blended/img.png", img)
    cv2.imwrite("blended_test/blended/fill.png", fill)
    cv2.imwrite("blended_test/blended/mask.png", mask)

    blended = cv2.seamlessClone(cropped_fill, img, mask, com, cv2.NORMAL_CLONE)
    return blended


# Crop image to it's roi (where it has color)
def crop_roi(img):
    coords = np.argwhere(img)
    x_min, y_min, _ = coords.min(axis=0)
    x_max, y_max, _ = coords.max(axis=0)
    cropped_img = img[x_min:x_max + 1, y_min:y_max + 1, :]
    return cropped_img.astype('uint8')


# Convert image as torch tensor to image as numpy array and normalize to 0-255
def to_np(tensor):
    tensor = tensor.clone()  # avoid modifying tensor in-place

    def norm_ip(img, min, max):
        img.clamp_(min=min, max=max)
        img.add_(-min).div_(max - min + 1e-5)

    def norm_range(t):
            norm_ip(t, float(t.min()), float(t.max()))

    norm_range(tensor)

    ndarr = tensor.mul(255).clamp(0, 255).byte().permute(1, 2, 0).cpu().numpy()
    return ndarr


def cv2_inpaint(masked_img, mask, num_channels, Tensor=None):
    inpainting_mask = 1 - mask
    inpainting_mask = to_np(inpainting_mask)
    masked_img = to_np(masked_img)

    if num_channels > 1:
        inpainting_mask = inpainting_mask[:, :, 0]

    src = masked_img
    msk = inpainting_mask
    inpainted = cv2.inpaint(np.uint8(src), np.uint8(msk), 3, cv2.INPAINT_NS)

    if Tensor is not None:
        # convert back to torch tensors
        inpainted = np.einsum('ijk->kij', inpainted)
        inpainted = Tensor(inpainted)

    return inpainted


# Apply alpha blend to batch
def cv2_inpaint_batch(masked_imgs, mask, num_channels, Tensor=None):
    ret = [cv2_inpaint(img, mask, num_channels, Tensor) for img in masked_imgs]
    if Tensor is not None:
        ret = torch.stack(ret)
    return ret
