import torch
from torch import nn
import numpy as np

from tqdm import tqdm
import utils
import psutil

from torchinfo import summary


class Network:
    def __init__(self, hypers, net_G, net_D):

        self.hypers = hypers
        self.net_G = net_G
        self.net_D = net_D

        # print(summary(net_G))

    def test(cls):
        alpha = cls.hypers.alpha
        print(alpha)

    def generate_sample(cls, data, mask):
        dim = data.shape[1]
        size = data.shape[0]

        Z = torch.rand((size, dim)) * 0.01
        missing_data_with_noise = mask * data + (1 - mask) * Z
        input_G = torch.cat((missing_data_with_noise, mask), 1).float()

        return cls.net_G(input_G)

    def _update_G(cls, batch, mask, hint, Z, loss, optimizer_G):
        loss_mse = nn.MSELoss(reduction="none")

        ones = torch.ones_like(batch)

        new_X = mask * batch + (1 - mask) * Z
        input_G = torch.cat((new_X, mask), 1).float()
        sample_G = cls.net_G(input_G)
        fake_X = new_X * mask + sample_G * (1 - mask)

        fake_input_D = torch.cat((fake_X, hint), 1).float()
        fake_Y = cls.net_D(fake_input_D)

        # print(batch, mask, ones.reshape(fake_Y.shape), fake_Y, loss(fake_Y, ones.reshape(fake_Y.shape).float()) * (1-mask), (loss(fake_Y, ones.reshape(fake_Y.shape).float()) * (1-mask)).mean())
        loss_G_entropy = (
            loss(fake_Y, ones.reshape(fake_Y.shape).float()) * (1 - mask)
        ).mean()
        loss_G_mse = (
            loss_mse((sample_G * mask).float(), (batch * mask).float())
        ).mean()

        loss_G = loss_G_entropy + cls.hypers.alpha * loss_G_mse

        optimizer_G.zero_grad()
        loss_G.backward()
        optimizer_G.step()

        return loss_G

    def _update_D(cls, batch, mask, hint, Z, loss, optimizer_D):
        new_X = mask * batch + (1 - mask) * Z

        input_G = torch.cat((new_X, mask), 1).float()

        sample_G = cls.net_G(input_G)
        fake_X = new_X * mask + sample_G * (1 - mask)
        fake_input_D = torch.cat((fake_X.detach(), hint), 1).float()
        fake_Y = cls.net_D(fake_input_D)

        loss_D = (loss(fake_Y.float(), mask.float())).mean()

        optimizer_D.zero_grad()
        loss_D.backward()
        optimizer_D.step()

        return loss_D

    def train_v2(cls, data, missing_header, ref_scaled):
        cpu = []
        ram = []
        ram_percentage = []

        dim = data.dataset_scaled.shape[1]
        train_size = data.dataset_scaled.shape[0]

        # loss = nn.BCEWithLogitsLoss(reduction = 'sum')
        loss = nn.BCELoss(reduction="none")
        loss_mse = nn.MSELoss(reduction="none")

        loss_D_values = np.zeros(cls.hypers.num_iterations)
        loss_G_values = np.zeros(cls.hypers.num_iterations)
        loss_MSE_train = np.zeros(cls.hypers.num_iterations)
        loss_MSE_test = np.zeros(cls.hypers.num_iterations)

        # for w in net_D.parameters():
        #    nn.init.normal_(w, 0, 0.02)
        # for w in net_G.parameters():
        #    nn.init.normal_(w, 0, 0.02)

        # for w in net_D.parameters():
        #    nn.init.xavier_normal_(w)
        # for w in net_G.parameters():
        #    nn.init.xavier_normal_(w)

        for name, param in cls.net_D.named_parameters():
            if "weight" in name:
                nn.init.xavier_normal_(param)
                # nn.init.uniform_(param)

        for name, param in cls.net_G.named_parameters():
            if "weight" in name:
                nn.init.xavier_normal_(param)
                # nn.init.uniform_(param)

        optimizer_D = torch.optim.Adam(cls.net_D.parameters(), lr=cls.hypers.lr_D)
        optimizer_G = torch.optim.Adam(cls.net_G.parameters(), lr=cls.hypers.lr_G)

        pbar = tqdm(range(cls.hypers.num_iterations))
        for it in pbar:

            mb_idx = utils.sample_idx(train_size, cls.hypers.batch_size)

            batch = data.dataset_scaled[mb_idx]
            mask_batch = data.mask[mb_idx]
            hint_batch = data.hint[mb_idx]
            ref_batch = ref_scaled[mb_idx]

            Z = torch.rand((cls.hypers.batch_size, dim)) * 0.01
            loss_D = cls._update_D(batch, mask_batch, hint_batch, Z, loss, optimizer_D)
            loss_G = cls._update_G(batch, mask_batch, hint_batch, Z, loss, optimizer_G)

            sample_G = cls.generate_sample(batch, mask_batch)

            loss_MSE_train[it] = (
                loss_mse(mask_batch * batch, mask_batch * sample_G)
            ).mean()

            loss_MSE_test[it] = (
                loss_mse((1 - mask_batch) * ref_batch, (1 - mask_batch) * sample_G)
            ).mean() / (1 - mask_batch).mean()

            if it % 100 == 0:
                s = f"{it}: loss D={loss_D.detach().numpy(): .3f}  loss G={loss_G.detach().numpy(): .3f}  rmse train={np.sqrt(loss_MSE_train[it]): .4f}  rmse test={np.sqrt(loss_MSE_test[it]): .3f}"
                pbar.clear()
                pbar.set_description(s)

            cpu.append(psutil.cpu_percent())
            ram.append(psutil.virtual_memory()[3] / 1000000000)
            ram_percentage.append(psutil.virtual_memory()[2])

            loss_D_values[it] = loss_D.detach().numpy()
            loss_G_values[it] = loss_G.detach().numpy()

        sample_G = cls.generate_sample(data.dataset_scaled, data.mask)
        data_train_imputed = data.dataset_scaled * data.mask + sample_G * (
            1 - data.mask
        )
        data_train_imputed = data.scaler.inverse_transform(
            data_train_imputed.detach().numpy()
        )

        utils.output(
            data_train_imputed,
            cls.hypers.output_folder,
            cls.hypers.output,
            missing_header,
            loss_D_values,
            loss_G_values,
            loss_MSE_train,
            loss_MSE_test,
            cpu,
            ram,
            ram_percentage,
            cls.hypers.override,
        )