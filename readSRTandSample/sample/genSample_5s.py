import numpy as np
import re
import math
import datetime
from collections import Counter
import random
import tqdm
from math import ceil
import os
from select_validdata import process_save_datavalid


# peep_listFiles = ['182_left_peep_1_series','182_left_peep_2_series','188_right_peep_1_series',
#                   '188_right_peep_2_series','01L-旁窥1115_series','01L-旁窥_series','01R-旁窥1115_series',
#                   '01R-旁窥_series', 'suda_left_peep_1_series', 'suda_left_peep_2_series', 
#                   'suda_right_peep_1_series', 'suda_right_peep_2_series'] # 12

peep_listFiles = ['01L-旁窥_series'] # 12


back_listFiles = ['182_left_back_1_series','182_left_back_2_series','188_right_back_1_series',
                  '188_right_back_2_series','02L-回头1_series','02L-回头2_series','02L-回头1115_series',
                  '02R-回头1_series','02R-回头2_series','02R-回头1115_series', 'suda_left_back_1_series', 
                  'suda_left_back_2_series', 'suda_right_back_1_series', 'suda_right_back_2_series'] # 14



passon_listFiles = ['182_left_passon_1_series','182_left_passon_2_series','182_left_passon_3_series',
                    '188_right_passon_1_series','188_right_passon_2_series','188_right_passon_3_series',
                    '03L-传递纸条1115_series','03L-传递纸条_series','03R-传递纸条1115_series','03R-传递纸条_series',
                    'suda_left_passon_0_series','suda_left_passon_1_series','suda_left_passon_2_series',
                    'suda_right_passon_0_series','suda_right_passon_1_series','suda_right_passon_2_series'] # 16



raise_listFiles = ['182_left_raise_1_series','182_left_raise_2_series','182_left_raise_3_series','182_left_raise_4_series',
                   '188_right_raise_1_series,','188_right_raise_2_series','188_right_raise_3_series','188_right_raise_4_series',
                   '05L_raise1_series','05L_raise2_series','05R_raise1_series','05R_raise2_series',
                   'suda_left_raise_1_series','suda_left_raise_2_series','suda_left_raise_3_series','suda_left_raise_4_series',
                   'suda_right_raise_1_series','suda_right_raise_2_series','suda_right_raise_3_series','suda_right_raise_4_series'] # 20



stand_listFiles = ['suda_left_stand_1_series','suda_left_stand_2_series','suda_right_stand_1_series','suda_right_stand_2_series', 
                   '182_left_stand_1_series','182_left_stand_2_series','188_right_stand_1_series','188_right_stand_2_series',
                   '04L_stand1_series','04L_stand2_series','04R_stand1_series','04R_stand2_series'] # 12


FPS_extractedVideo = 3  #所标注样本的帧率
interval_inSample = 1  #浮点数，生成最终用于训练的样本时，对series的采样间隔.(即中间空`interval_inSample-1`帧)
totalTimeLength = 15 #EGCN模型的时间维度大小
threshold_percentNonZero = 0.85 #容许的最低有效识别率（有效帧数(非零帧)占总EGCN的长度）
threshold_stdMeanTotal = 1 #这里取负值是为了对任意幅度的都采样，即不动的样本(std为0的)也不过滤。
ceilNumSamplesPerStu = 1   #对一个学生样本所作的总采样个数上限，最小1
floorClipPercent = 0.85 #一个作弊片段最少采样帧数比例为多少时，该样本还认为有效。大于采样帧数的0.85以上意味着不能低于无效帧不能超过两帧
num_zeroSamples = 1 #对于非预警类别(normal类别)中，全零样本的构造个数。
whether_existNoneValidTime = False #是否需要校验有无起、终帧标签。对于存在非考试时段的视频，需要作此校验。


# 以下内容无需更改，仅需设置上边参数即可
#######################################
class oneSample: # 处理一个目标从头到尾的所有样本
    # sample=oneSample(lenTotal,sampleDict[key],series[:,[key],:,:],startBias)
    def __init__(self,data_total_len, single_object_all_time, single_object_all_data, object_order):
        '''
        data_total_len:             数据总时长、帧数
        single_object_all_time:     单个目标所有标注有动作的时间段
        single_object_all_data:     单个目标从头到尾的所有数据
        '''
        self.data_total_len = data_total_len #series的总长度(帧数)
        self.single_object_all_data = single_object_all_data #timeStepLength,numStudents(1),10,2
        self.single_object_all_time_list = single_object_all_time #[(label,start,end),...], end是按照python的规则，即end=最后一帧标号+1
        self.behav_noLabel_list = self.cal_complementarySet() # [(start,end),...] # 这里是获取未发生动作的时间段——>normal
        self.object_order = object_order

    def cal_complementarySet(self):
        '''
        获取没有标注时间段标签, 即normal时间段
        '''
        behav_noLabel = []
        ptr = 0
        for item in self.single_object_all_time_list:
            start = item[1]
            if start - 1 > ptr:
                behav_noLabel.append((ptr,start))
            ptr = item[2]
        if self.data_total_len - 1 > ptr:
            behav_noLabel.append((ptr, self.data_total_len))
        return behav_noLabel

    def getData(self, key, file_name):

        data = dict()
        numLabels = len(self.single_object_all_time_list)

        for i,timeSlot in enumerate(self.single_object_all_time_list):
            start = timeSlot[1] if timeSlot[1] >= 0 else 0
            end = timeSlot[2] if timeSlot[2] <= self.data_total_len else self.data_total_len
            assert end>start, "Error: end <= start."
            if i == 0:
                availStart = 0
            else:
                availStart = self.single_object_all_time_list[i-1][2]
                availStart = availStart if availStart < start else start
            if i == numLabels - 1:
                availEnd = self.data_total_len
            else:
                availEnd = self.single_object_all_time_list[i+1][1]
                availEnd = availEnd if availEnd <= self.data_total_len else self.data_total_len
                availEnd = availEnd if availEnd > end else end

            start = int((start-availStart) / interval_inSample) # 标注的动作开始时间，即实际开始动作时间
            end = ceil((end-availStart) / interval_inSample) + 1  # 标注的动作结束时间，即实际结束动作时间
            dataTemp = self.single_object_all_data[availStart:availEnd:interval_inSample] # 待采样序列，
            end = end if len(dataTemp) >= end else len(dataTemp) # 待采样的序列长度大于实际的结束时间
            dataTemp = self.gen_onePieceData(dataTemp, start, end, key, file_name, timeSlot[0])
            if dataTemp is not None:
                label = timeSlot[0]
                if label not in data:
                    data[label]=[]
                data[label]+=dataTemp
        return data

    def getNormalData(self):
        data = []
        for i, timeSlot in enumerate(self.behav_noLabel_list):
            avail_interval_inSample = interval_inSample
            if interval_inSample - int(interval_inSample) > 0.0:
                if random.randint(0, 1) == 0:
                    avail_interval_inSample = int(interval_inSample)
                else:
                    avail_interval_inSample = ceil(interval_inSample)
            else:
                avail_interval_inSample = int(avail_interval_inSample)
            dataTemp = self.single_object_all_data[timeSlot[0]:timeSlot[1]:avail_interval_inSample]
            end = len(dataTemp)
            dataTemp = self.gen_onePieceData_normal(dataTemp, 0, end) # 对没有动作样本的采样梳理
            if dataTemp is not None:
                data += dataTemp
        #下边构造全零样本
        data.append(np.zeros((totalTimeLength, num_zeroSamples, 10, 2)))
        return data

    def gen_onePieceData(self, dataTemp, start, end, key, file_name, beha_label):
        '''
        dataTemp:      单独的一段，非标注时段 + 标注时段 + 非标注阶段
        start:         标注时段相对开始时刻
        end:           标注时段相对结束时刻
        标注的动作片段的起、终帧标号(相对于dataTemp,从0开始. 终帧+1,符合python规则)
        key:           目标序号
        '''
        # start、end：
        dataValid = dataTemp[start:end]
        threshold_numNonZero = dataValid.shape[0] * threshold_percentNonZero # 在有效的片段内含0的阈值
        # 在起始动作片段内，超过5%没有目标的话，就不要本片段
        # 下边检测零值占比
        numNonZeros = Counter(np.where((dataValid ** 2).sum(axis=-1).sum(axis=-1) > 0.0)[-1])[0]
        if numNonZeros < threshold_numNonZero: ## 中间可能出现几帧的坐标可能出现0
           return None
        # 下边检测动作幅度
        stdStus = np.mean((dataValid.std(axis=0).mean(axis=-1)), axis=-1)[0]
        if stdStus <= threshold_stdMeanTotal: # 不动的样本等于0的话，或者全0的样本去掉            
            return None
        data=[]
        # 在时间维度进行采样，不手动指定每个样本的采样个数，根据有效样本的长度大小自适应决定采样个数
        # 需要比较（end-start）和 totalTimeLength的大小，
        save_path = f'./out_raise/{beha_label}/{file_name}/{key}'
        npy_file_path = process_save_datavalid(save_path, dataValid, self.object_order)
        # 如果save_path 中没有该文件，不做下面的操作
        # if not os.path.exists(npy_file_path):
        #     return None
        sample_data = self.doRandomClipAndAmpli(dataTemp, start, end)
        self.object_order += 1
        
        # 不管前后为0的样本，跳过此类样本
        frames, targets, _, _ = sample_data.shape
        for target in range(targets):
            data_info = sample_data[:,[target],:,:]
            target_numNonZeros = Counter(np.where((data_info ** 2).sum(axis=-1).sum(axis=-1) > 0.0)[-1])[0]
            # print('target_numNonZeros:',target_numNonZeros)
            if target_numNonZeros >= totalTimeLength - 2:  ## 中间可能出现几帧的坐标都为0,两头也可能出现0，超过两帧目标丢失，就把此目标丢掉
                ## 这里的逻辑需要变一下，最理想的状况是15帧都不为0，
                ## 最多会出现2帧为0的状况，先考虑只有一帧为0的情况，那么target_numNonZeros==14
                if target_numNonZeros == totalTimeLength - 1:
                    for frame in range(frames):
                        if (np.expand_dims(data_info[frame,:,:,:], axis=0) ** 2).sum(axis=-1).sum(axis=-1) == 0.0:
                            if frame == 0:
                                data_info[frame,:,:,:] = data_info[frame+1,:,:,:]

                            elif frame == totalTimeLength - 1:
                                data_info[frame,:,:,:] = data_info[frame-1,:,:,:]# 如果为0的位置出现在两头，也要给他补齐

                            else:
                                data_info[frame,:,:,:] = (data_info[frame-1,:,:,:]+data_info[frame+1,:,:,:])/2 #如果出现在中间的话，需要结合前后帧取均值

                ## 不等于14，就等于13
                elif target_numNonZeros == totalTimeLength - 2:
                    frame_index_zero = [] # 寻找为0的索引
                    for frame in range(frames):
                        if (np.expand_dims(data_info[frame,:,:,:], axis=0) ** 2).sum(axis=-1).sum(axis=-1) == 0.0:
                            frame_index_zero.append(frame)
                    assert len(frame_index_zero) == 2, "Error: len(frame_index_zero) != 2."
                    if frame_index_zero == [0,1]:
                        data_info[0,:,:,:] = data_info[2,:,:,:]
                        data_info[1,:,:,:] = data_info[2,:,:,:]

                    elif frame_index_zero == [totalTimeLength - 2, totalTimeLength - 1]:
                        data_info[totalTimeLength - 2,:,:,:] = data_info[totalTimeLength - 3,:,:,:]
                        data_info[totalTimeLength - 1,:,:,:] = data_info[totalTimeLength - 3,:,:,:]

                    elif frame_index_zero == [0, totalTimeLength - 1]: 
                        data_info[0,:,:,:] = data_info[1,:,:,:]
                        data_info[totalTimeLength - 1,:,:,:] = data_info[totalTimeLength - 2,:,:,:]

                    elif frame_index_zero[0] == 0: # 有一帧出现在开始，另一帧肯定在中间，取均值
                        data_info[frame_index_zero[0],:,:,:] = data_info[1,:,:,:]
                        data_info[frame_index_zero[1],:,:,:] = (data_info[frame_index_zero[1]-1,:,:,:]+data_info[frame_index_zero[1]+1,:,:,:])/2

                    elif frame_index_zero[1] == totalTimeLength - 1: # 有一帧出现在结尾，另一帧肯定在中间，取均值
                        data_info[frame_index_zero[1],:,:,:] = data_info[-2,:,:,:]
                        data_info[frame_index_zero[0],:,:,:] = (data_info[frame_index_zero[0]-1,:,:,:]+data_info[frame_index_zero[0]+1,:,:,:])/2

                    elif frame_index_zero[1] - frame_index_zero[0] != 1: #漏检两帧在中间且不连续，两帧都取均值
                        data_info[frame_index_zero[0],:,:,:] = (data_info[frame_index_zero[0]-1,:,:,:]+data_info[frame_index_zero[0]+1,:,:,:])/2
                        data_info[frame_index_zero[1],:,:,:] = (data_info[frame_index_zero[1]-1,:,:,:]+data_info[frame_index_zero[1]+1,:,:,:])/2

                    else: # 漏检的两帧在中间且连续，则两边赋值
                        data_info[frame_index_zero[0],:,:,:] = data_info[frame_index_zero[0]-1,:,:,:]
                        data_info[frame_index_zero[1],:,:,:] = data_info[frame_index_zero[0]+1,:,:,:]
                data.append(data_info)
            else:
                continue
        return data
    
    def gen_onePieceData_normal(self,series,start,end):
        # series是包括正常动作的完整片段
        # start、end：标注的动作片段的起、终帧标号（相对于series，从0开始. 终帧+1,符合python规则）
        dataValid = series[start:end]
        threshold_numNonZero = dataValid.shape[0] * threshold_percentNonZero # 在有效的片段内含0的阈值
        # 在起始动作片段内，超过5%没有目标的话，就不要本片段
        # 下边检测零值占比
        numNonZeros = Counter(np.where((dataValid ** 2).sum(axis=-1).sum(axis=-1) > 0.0)[-1])[0]
        if numNonZeros < threshold_numNonZero: ## 中间可能出现几帧的坐标可能出现0
           return None
        # 下边检测动作幅度
        stdStus = np.mean((dataValid.std(axis=0).mean(axis=-1)), axis=-1)[0]
        if stdStus <= threshold_stdMeanTotal: # 不动的样本等于0的话，或者全0的样本去掉            
            return None
        # 对学生进行复制，达到扩增数据集的目的
        # numSamples=0
        # for _ in range(ceil(dataValid.shape[0] / totalTimeLength)): 
        #     # 对于有动作的正样本来说，采样数最多不会超过2个
        #     numSamples += random.randint(1, ceilNumSamplesPerStu)
        data=[]

        # 在时间维度进行采样，不手动指定每个样本的采样个数，根据有效样本的长度大小自适应决定采样个数
        # 需要比较（end-start）和 totalTimeLength的大小，
        sample_data = self.doRandomClipAndAmpli_normal(data=series, start=start, end=end)
        
        # 不管前后为0的样本，跳过此类样本
        frames, targets, _, _ = sample_data.shape
        for target in range(targets):
            data_info = sample_data[:,[target],:,:]
            target_numNonZeros = Counter(np.where((data_info ** 2).sum(axis=-1).sum(axis=-1) > 0.0)[-1])[0]
            # print('target_numNonZeros:',target_numNonZeros)
            if target_numNonZeros >= totalTimeLength - 2:  ## 中间可能出现几帧的坐标都为0,两头也可能出现0，超过两帧目标丢失，就把此目标丢掉
                ## 这里的逻辑需要变一下，最理想的状况是15帧都不为0，
                ## 最多会出现2帧为0的状况，先考虑只有一帧为0的情况，那么target_numNonZeros==14
                if target_numNonZeros == totalTimeLength - 1:
                    for frame in range(frames):
                        if (np.expand_dims(data_info[frame,:,:,:], axis=0) ** 2).sum(axis=-1).sum(axis=-1) == 0.0:
                            if frame == 0:
                                data_info[frame,:,:,:] = data_info[frame+1,:,:,:]

                            elif frame == totalTimeLength - 1:
                                data_info[frame,:,:,:] = data_info[frame-1,:,:,:]# 如果为0的位置出现在两头，也要给他补齐

                            else:
                                data_info[frame,:,:,:] = (data_info[frame-1,:,:,:]+data_info[frame+1,:,:,:])/2 #如果出现在中间的话，需要结合前后帧取均值

                ## 不等于14，就等于13
                elif target_numNonZeros == totalTimeLength - 2:
                    frame_index_zero = [] # 寻找为0的索引
                    for frame in range(frames):
                        if (np.expand_dims(data_info[frame,:,:,:], axis=0) ** 2).sum(axis=-1).sum(axis=-1) == 0.0:
                            frame_index_zero.append(frame)
                    assert len(frame_index_zero) == 2, "Error: len(frame_index_zero) != 2."
                    if frame_index_zero == [0,1]:
                        data_info[0,:,:,:] = data_info[2,:,:,:]
                        data_info[1,:,:,:] = data_info[2,:,:,:]

                    elif frame_index_zero == [totalTimeLength - 2, totalTimeLength - 1]:
                        data_info[totalTimeLength - 2,:,:,:] = data_info[totalTimeLength - 3,:,:,:]
                        data_info[totalTimeLength - 1,:,:,:] = data_info[totalTimeLength - 3,:,:,:]

                    elif frame_index_zero == [0, totalTimeLength - 1]: 
                        data_info[0,:,:,:] = data_info[1,:,:,:]
                        data_info[totalTimeLength - 1,:,:,:] = data_info[totalTimeLength - 2,:,:,:]

                    elif frame_index_zero[0] == 0: # 有一帧出现在开始，另一帧肯定在中间，取均值
                        data_info[frame_index_zero[0],:,:,:] = data_info[1,:,:,:]
                        data_info[frame_index_zero[1],:,:,:] = (data_info[frame_index_zero[1]-1,:,:,:]+data_info[frame_index_zero[1]+1,:,:,:])/2

                    elif frame_index_zero[1] == totalTimeLength - 1: # 有一帧出现在结尾，另一帧肯定在中间，取均值
                        data_info[frame_index_zero[1],:,:,:] = data_info[-2,:,:,:]
                        data_info[frame_index_zero[0],:,:,:] = (data_info[frame_index_zero[0]-1,:,:,:]+data_info[frame_index_zero[0]+1,:,:,:])/2

                    elif frame_index_zero[1] - frame_index_zero[0] != 1: #漏检两帧在中间且不连续，两帧都取均值
                        data_info[frame_index_zero[0],:,:,:] = (data_info[frame_index_zero[0]-1,:,:,:]+data_info[frame_index_zero[0]+1,:,:,:])/2
                        data_info[frame_index_zero[1],:,:,:] = (data_info[frame_index_zero[1]-1,:,:,:]+data_info[frame_index_zero[1]+1,:,:,:])/2

                    else: # 漏检的两帧在中间且连续，则两边赋值
                        data_info[frame_index_zero[0],:,:,:] = data_info[frame_index_zero[0]-1,:,:,:]
                        data_info[frame_index_zero[1],:,:,:] = data_info[frame_index_zero[0]+1,:,:,:]
                data.append(data_info)
            else:
                continue
        return data
    
    def doRandomClipAndAmpli_normal(self, data, start, end):

        totalLen = data.shape[0]
        validLen = end - start
        clipLen = min(\
            random.randint(int(validLen * floorClipPercent), validLen), totalTimeLength)
        data_start = start
        # if validLen > clipLen:
        #     data_start += random.randint(0, validLen-clipLen)
        validLen = clipLen
        dataNew = np.zeros((totalTimeLength, 1, 10, 2)) # 构造一个45帧的全0样本
        random_min = end - totalTimeLength
        # print("#########", totalLen, random_min, validLen, start, end)
        if random_min < 0:
            random_min = 0

        availStart = 0
        if random_min < data_start:
            availStart = random.randint(random_min, data_start)

        start_valindInNew = 0
        # print("!!!!!!!!", availStart, random_min, validLen, start, end)
        if data_start - availStart <= totalTimeLength - validLen:
            start_valindInNew = data_start-availStart
        #有`InNew`标识的表示是在dataNew中的标号。
        # totalLen = min(totalTimeLength-start_valindInNew, totalLen-availStart)
        if totalLen < availStart + totalTimeLength:
            totalLen = totalLen-availStart
        else:
            totalLen = totalTimeLength

        totalLen_InNew = totalLen
        availstart_InNew = 0
        leftLenAmpli=0
        rightLenAmpli=0
        if totalLen < totalTimeLength:
            voidLen = totalTimeLength - totalLen
            leftLenAmpli = random.randint(0, voidLen)
            rightLenAmpli = random.randint(0, voidLen - leftLenAmpli)
            totalLen_InNew = leftLenAmpli + totalLen + rightLenAmpli
            availstart_InNew = random.randint(0, totalTimeLength - totalLen_InNew)
        # print("----------", availStart, availStart + totalLen, data_len, start, end)
        dataNew[availstart_InNew:availstart_InNew+totalLen_InNew] = np.concatenate(
            [np.repeat(data[[availStart]], leftLenAmpli, axis=0), \
             data[availStart:availStart+totalLen], \
             np.repeat(data[[availStart+totalLen-1]], rightLenAmpli, axis=0)], \
            axis=0)
        #为了避免大量样本都包括0，这里再额外产生一个无零存在的样本
        if totalLen_InNew<totalTimeLength:
            dataNew_nonZero =np.concatenate(
                [np.repeat(data[[availStart]], availstart_InNew+leftLenAmpli, axis=0), \
                 data[availStart:availStart + totalLen], \
                 np.repeat(data[[availStart + totalLen - 1]], \
                    totalTimeLength-totalLen_InNew-availstart_InNew+rightLenAmpli, axis=0)], \
                axis=0)
            dataNew = np.concatenate([dataNew, dataNew_nonZero], axis=1)
        # 下边以1/5的概率新增一个采样：非标注时段全补零。
        if random.randint(0, 4) == 0:
            ampliSample = np.zeros((totalTimeLength, 1, 10, 2))
            ampliSample[start_valindInNew:start_valindInNew + validLen] = \
                data[data_start:data_start + validLen]
            # print(start_valindInNew,data_start,validLen,data.shape[0])
            dataNew = np.concatenate([dataNew, ampliSample], axis=1)
        return dataNew

    def doRandomClipAndAmpli(self, data, start, end):
        '''
        输入：
        data: 非标注阶段 + 标注阶段 + 非标注阶段 数据
        start: 标注其实阶段, 在这一段的开始时间
        end: 标注结束阶段，在这一段的结束时间
        输出：
        data_valid:[15, num, 10, 2], 输出数据是一个目标的滑动窗口采样数据，num都是一个人的数据，只是起止时间不一样
        '''
        total_len = data.shape[0]
        valid_len = end - start
        # print(f'start:{start},end:{end},valid_len:{valid_len},total_len:{total_len},left_len:{left_len},right_len:{right_len}')
        # 默认情况下标注时间段不会超过5s
        # 如果相等的话，直接返回这一个有效片段数据即可
        if valid_len == totalTimeLength:
            dataNew = np.zeros((totalTimeLength, 1, 10, 2)) # 构造一个15帧的全0样本
            dataNew = data[start:end, :, :, :]
        # 如果超过5s，datanew数据在valid_data上滑动
        elif valid_len > totalTimeLength:
            dataNew = np.zeros((totalTimeLength, valid_len - totalTimeLength + 1, 10, 2))
            for i in range(0,valid_len - totalTimeLength + 1):
                dataNew[:,[i],:,:] = data[start+i:start+i+totalTimeLength,:,:,:]
        
        # TODO 有效片段长度小于15帧
        else: # valid_len < totalTimeLength, valid_data在dataNew上滑动，前后空余的部分补齐
            dataNew  = np.zeros((totalTimeLength, totalTimeLength - valid_len + 1 , 10, 2))
            for i in range(totalTimeLength - valid_len + 1):
                # 先处理左边
                if start-i >= 0 and total_len - (start-i) >= totalTimeLength:
                    dataNew[:,[i],:,:] = data[start-i:start-i+totalTimeLength,:,:,:]
                elif start-i < 0 and total_len >= totalTimeLength: # 假设右边有充足的数据，左边重复（i-start）个片段，重复的是第一帧的数据
                    leftdata = np.repeat(data[[0],:,:,:], i-start, axis=0)
                    dataNew[:,[i],:,:] = np.concatenate([leftdata,data[:totalTimeLength-(i-start),:,:,:]],axis=0)
                elif start-i < 0 and total_len < totalTimeLength:
                    leftdata = np.repeat(data[[0],:,:,:], i-start, axis=0)
                    right_repeat_len = totalTimeLength-total_len-(i-start) if (totalTimeLength-total_len-(i-start)) >= 0 else 0
                    rightdata = np.repeat(data[[-1],:,:,:], right_repeat_len, axis=0)
                    dataNew[:,[i],:,:] = np.concatenate([leftdata,data[:(totalTimeLength-(i-start)-right_repeat_len)],rightdata],axis=0)
                # 开始处理右边,左边在滑动过程中始终保持大于0状态
                elif start - i > 0 and total_len - (start-i) < totalTimeLength:
                    rightdata = np.repeat(data[[-1],:,:,:], (totalTimeLength-(total_len-(start-i))), axis=0)
                    dataNew[:,[i],:,:] = np.concatenate([data[start - i:,:,:,:],rightdata],axis=0)
             
        return dataNew 

def read_srt_file_gen(file):
    with open(file, "r", encoding='gb18030', errors='ignore') as fs:
        for data in fs.readlines():
            yield data

def retrieveLabel(npy_file, numSamples, fps):
    srt_file = npy_file.split('_series')[0]+'.srt'
    fileGen = read_srt_file_gen(srt_file)
    Max_lenTime = 0.0           # 该文件中标注最长的一段动作时长
    sampleDict = dict()
    for i in range(numSamples):
        sampleDict[i]=[]        # 人数
    while True:
        try:
            item = next(fileGen)
            if "--> " in item:
                time_arr = item.split('--> ')
                start_time = time_arr[0].replace(" ", "")
                end_time = time_arr[1].replace(" ", "").replace("\n", "")
                start_time = datetime.datetime.strptime(start_time + "0", "%H:%M:%S,%f")
                end_time = datetime.datetime.strptime(end_time + "0", "%H:%M:%S,%f")
                start = start_time.hour * 3600 + start_time.minute * 60 + start_time.second + start_time.microsecond * 0.000001
                end = end_time.hour * 3600 + end_time.minute * 60 + end_time.second + end_time.microsecond * 0.000001
                lenTimeTemp = end - start
                if lenTimeTemp > Max_lenTime:
                    Max_lenTime = lenTimeTemp
                start = max(int(start * fps)-1, 0)
                end = ceil(end * fps)
                assert end > start, f'Wrong: `end` dosen\'t large than `start`. {item}'
                label = next(fileGen).replace(" ", "").replace("\n", "")
                nextLine = next(fileGen).replace(" ", "").replace("\n", "")
                if nextLine=="" or nextLine != "":
                    for key in sampleDict.keys():
                        sampleDict[key].append((label, start, end))
                    continue
        except StopIteration:
            break
    return sampleDict, Max_lenTime

if __name__ == '__main__':
    Max_lenTime = 0.0 # 该文件中标注最长的一段动作时长
    dataDict=dict()   # 键为数据类型，值为相对类型的数据
    dataDict['normal']=[]
    npy_root_path = '/home/goldsun/data/genData/npy/raise'
    for root, dirs,files in os.walk(npy_root_path):
        for file in files:
            if file.split('.')[0] in stand_listFiles:
                npy_file = os.path.join(root,file) # npy_file = /home/goldsun/data/genData/npy/stand/182-188_stand/*.npy
            elif file.split('.')[0] in peep_listFiles:
                npy_file = os.path.join(root,file) # npy_file = /home/goldsun/data/genData/npy/stand/182-188_stand/*.npy
            elif file.split('.')[0] in back_listFiles:
                npy_file = os.path.join(root,file) # npy_file = /home/goldsun/data/genData/npy/stand/182-188_stand/*.npy
            elif file.split('.')[0] in passon_listFiles:
                npy_file = os.path.join(root,file) # npy_file = /home/goldsun/data/genData/npy/stand/182-188_stand/*.npy
            elif file.split('.')[0] in raise_listFiles:
                npy_file = os.path.join(root,file) # npy_file = /home/goldsun/data/genData/npy/stand/182-188_stand/*.npy
            else:
                continue
            print(f"Deal with {npy_file}:")
            object_order = 0
            series = np.load(npy_file) 
            data_total_len = series.shape[0]
            sampleDict,lenTimeTemp = retrieveLabel(npy_file, series.shape[1], FPS_extractedVideo)
            # print(sampleDict)
            if lenTimeTemp > Max_lenTime:
                Max_lenTime = lenTimeTemp
            for key in tqdm.tqdm(sampleDict.keys()): 
                # lenTotal: npy文件的总时长、总帧数
                # key： npy文件中的目标数，第key个目标
                # series[:,[key],:,:]：目标key的所有数据
                single_object_all_time_list = sampleDict[key]     # 单个目标标注的所有时间
                single_object_all_data = series[:,[key],:,:] # 单个目标所有数据
                sample=oneSample(data_total_len, single_object_all_time_list, single_object_all_data, object_order)
                dataTemp = sample.getData(key, file.replace('.npy',''))
                dataDict['normal'] += sample.getNormalData()
                for label in dataTemp.keys():
                    if label not in dataDict:
                        dataDict[label]=[]
                    dataDict[label]+=dataTemp[label]
    print("\nSaving...")
    for key in tqdm.tqdm(dataDict.keys()):
        print(key, len(dataDict[key]))
        if len(dataDict[key]) == 0:
            continue
        data = np.concatenate(dataDict[key], axis=1)
        # if key == 'normal':
            # continue
        # 归一化
        # xyMinT: 所有帧每一个目标，分别取X_min，Y_min,
        # xyMaxT: 所有帧每一个目标，分别取X_max，Y_max,
        # xyLen: 所有帧每一个目标，x方向最大和最小的差值以及y方向上最大和最小的差值
        # xyMax: 每个目标，在所有帧（45）中x方向最大和最小的差值以及y方向上最大和最小的差值，取最大的一帧，不同的目标，得到的最大值不一定是同一帧的，大概率属于不同的帧
        # padT： 每个目标，最大的一帧xy方向的差值，分别与45帧，每个目标最大xy方向差值作差除以2，为每个目标的坐标点作padding
        # 所有帧每一个目标，分别取X_min，Y_min, X_max, Y_max 保存成xyMinT，xyMaxT
        # 相减之后得到，所有帧，每一个目标，x方向最大和最小的差值以及y方向上最大和最小的差值

        ## 修改归一化条件，各自样本的归一化缺少了空间信息，每个样本都是一个独立个体，修改成与空间相关的归一化
        data_x = data[...,0]
        data_y = data[...,1]
        data_with_position = np.stack((data_x / 1920, data_y / 1080), axis= -1)

        xyMinT = np.min(data, axis=2, keepdims=True)
        xyLenT = np.max(data, axis=2, keepdims=True) - xyMinT
        # (timeStepLength, numStudents, 1, 2)
        ## 每个目标在45帧中的最大差值
        xyMax = np.max(xyLenT, axis=0, keepdims=True)  # (1, numStudents, 1, 2)
        padT = (xyMax - xyLenT) * 0.5  # (timeStepLength, numStudents, 1, 2)
        data = (padT + data - xyMinT) / (xyMax + 1e-6)

        #Save
        np.save('./out/' + key + '_single_normalize.npy', data)  # shape: N,C,T,V
        np.save('./out/' + key + '_global_normalize.npy', data_with_position)  # shape: N,C,T,V
    print('\nAll Done.')
    print(f'Max time len: {Max_lenTime}s.')