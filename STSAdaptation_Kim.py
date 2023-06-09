import random
import numpy as np
import time

num_states = 6  # 연결된 STA 수 (0-5)
num_actions = 3  # 증가, 감소, 그대로 유지
q_table = np.zeros((num_states, num_actions))

learning_rate = 0.1
discount_factor = 0.99
exploration_rate = 1.0
exploration_rate_decay = 0.001


def choose_action(state):
    if np.random.uniform(0, 1) < exploration_rate:
        return np.random.randint(num_actions)
    else:
        return np.argmax(q_table[state])

def update_q_table(state, action, reward, next_state):
    q_table[tuple(state), action] = q_table[tuple(state), action] + learning_rate * (
            reward + discount_factor * np.max(q_table[tuple(next_state)]) - q_table[tuple(state), action])

def get_reward(successful_ssw_count, total_ssw_count):
    return successful_ssw_count / total_ssw_count

# 충돌이 발생한 프레임의 SINR 값을 상태에 포함시키기 위한 새로운 상태 함수를 정의합니다.
def get_new_state(connected_stations, sinr_values):
    sinr_values_filtered = [x for x in sinr_values if not np.isnan(x)]  # NaN 값을 제외한 리스트 생성
    sinr_mean = np.mean(sinr_values_filtered) if sinr_values_filtered else 0  # 리스트가 비어있을 경우 0을 할당
    state = np.array([connected_stations, sinr_mean], dtype=np.int32)
    return state


def SINR(received_signal, interfering_signals, noise_power=1e-9):
    interference = sum(interfering_signals)
    return received_signal / (interference + noise_power)



def SNR():
    # 신호 레벨 범위 (dBm 단위)
    min_signal_level = -80
    max_signal_level = -40

    # 무작위 신호 레벨 개수
    num_signal_levels = 5

    # 무작위 신호 레벨 생성
    random_signal_levels = np.random.uniform(min_signal_level, max_signal_level, num_signal_levels)
    print("Random signal levels (dBm):", random_signal_levels)
    return random_signal_levels

STS = 32


class AccessPoint:
    def __init__(self, num_stations):
        self.num_stations = num_stations
        self.num_sector = 6
        self.stations = [Station(i) for i in range(num_stations)]
        self.sinr_values = [[] for _ in range(self.num_sector)]

    def start_beamforming_training(self):
        self.sinr_values = []

        beacon_frame = self.create_beacon_frame_with_trn_r()
        for station in self.stations:
            station.receive_bti(beacon_frame)
            station.receive_trn_r(beacon_frame)

    def create_beacon_frame_with_trn_r(self):
        return {'SNR': SNR(), 'trn_r': 'TRN-R data'}

    def recieve(self, sector):
        successful_ssw_count = 0
        received_signals = []
        if sector >= len(self.sinr_values):
            return [], successful_ssw_count  # successful_ssw_count를 리스트가 아닌 정수로 반환
        for i in range(STS):
            for station in self.stations:
                if not station.pair and sector == station.tx_sector_AP:
                    signal = station.send_ssw(i, sector)
                    if signal is not None:
                        received_signals.append(signal)
                    if station.data_success:
                        successful_ssw_count += 1
            if len(received_signals) > 1:
                sinr_values = [SINR(signal, [s for s in received_signals if s != signal]) for signal in received_signals]
                self.sinr_values[sector].extend(sinr_values)
        if not self.sinr_values[sector]:
            return [], successful_ssw_count  # successful_ssw_count를 리스트가 아닌 정수로 반환
        else:
            return self.sinr_values[sector], successful_ssw_count  # successful_ssw_count를 리스트가 아닌 정수로 반환

    def broadcast_ack(self):
        ack_frame = "ACK_DATA"
        for station in self.stations:
            if station.pair == False:
                station.receive_ack_frame(ack_frame)

    def next_bi(self):
        self.start_beamforming_training()
        for i in range(self.num_sector):
            successful_ssw_count, sinr_values = self.recieve(i)  # sinr_values 반환값 추가
        self.broadcast_ack()

    def all_stations_paired(self):
        return all(station.pair for station in self.stations)

class Station:
    def __init__(self, id):
        self.id = id
        self.pair = False
        self.tx_sector_AP = None
        self.rx_sector = None
        self.collisions = 0
        self.data_success = False
        self.sectors = [i for i in range(1, 5)]
        self.backoff_count = random.randint(1, STS)

    def receive_bti(self, beacon_frame):
        self.tx_sector_AP = self.get_best_sectors(beacon_frame)
        print(f"Station {self.id}: Best TX sector of AP - {self.tx_sector_AP}")

    def get_best_sectors(self, beacon_frame):
        snr_values = beacon_frame['SNR']
        best_sector = np.argmax(snr_values) + 1
        return best_sector

    def receive_trn_r(self, beacon_frame):
        best_rx_sector = self.get_best_rx_sector(beacon_frame)
        self.rx_sector = best_rx_sector  # rx_sector에 할당하는 부분 추가
        print(f"Station {self.id}: Best RX sector of STA after TRN-R - {best_rx_sector}")

    def get_best_rx_sector(self, beacon_frame):
        snr_values = SNR()
        best_rx_sector = np.argmax(snr_values) % len(self.sectors) + 1
        return best_rx_sector

    def send_ssw(self, STS, sector):
        if not self.pair and STS == self.backoff_count:  # 이미 연결된 STA들이 참여하지 않도록 조건 추가
            self.rx_sector = None
            self.data_success = True
            print("Station " + str(self.id) + " transmitted SSW frame successfully")
            return random.uniform(0.0001, 0.001)  # 임의의 수신 신호 전송
        return None

    def receive_ack_frame(self, ack_frame):
        if self.pair == False:
            if self.data_success == True:
                self.pair = True
                print("Station " + str(self.id) + " received ACK successfully")
        else:
            print("Station " + str(self.id) + " did not receive ACK, will retry in the next BI")

total_STS_used = 0  # 누적된 STS 수를 저장할 변수 추가

for episode in range(20):
    AP = AccessPoint(num_stations=5)
    connected_stations = 0
    total_time = 0
    total_STS_used = 0  # 에피소드가 시작시 누적된 STS 값을 초기화
    start_time = time.time()
    s_time = time.time()
    AP.start_beamforming_training()

    while not AP.all_stations_paired():

        sinr_values = []
        connected_stations = sum(station.pair for station in AP.stations)
        state = get_new_state(connected_stations, sinr_values)
        total_STS_used += STS  # 누적 STS 값 업데이트

        action = choose_action(state)
        if action == 0:
            STS = min(32, STS + 1)  # STS 개수를 최대 32개로 제한
        elif action == 1:
            STS = max(1, STS - 1)

        successful_ssw_count = 0
        sinr_values = []
        for i in range(AP.num_sector):
            sinr_values_sector, successful_ssw_count_sector = AP.recieve(i)
            if sinr_values_sector:  # Check if the list is not empty
                sinr_values.extend(sinr_values_sector)
            successful_ssw_count += successful_ssw_count_sector

        AP.broadcast_ack()

        if not AP.all_stations_paired():
            print("Not all stations are paired. Starting next BI process.")

            f_time = time.time()  # 시간을 할당하는 부분 추가
            time_difference = f_time - s_time
            s_time += time_difference
            reward = get_reward(successful_ssw_count, STS)
            connected_stations = sum(station.pair for station in AP.stations)
            next_state = get_new_state(connected_stations, sinr_values)

            update_q_table(state, action, reward, next_state)

            AP.next_bi()

    end_time = time.time()  # 시뮬레이션 종료 시간 측정
    total_time = end_time - start_time
    print("EPISODE: " + str(episode) + " All stations are paired. Simulation complete.")
    print(f"Total simulation time: {total_time:.3f} seconds")
    # 결과를 파일에 저장
    with open('beamforming_simulation_results_with_kim.txt', 'a') as f:
        f.write(f"{total_time:.3f}, {total_STS_used}\n")  # 누적된 STS 값을 함께 저장

    exploration_rate = max(0.01, exploration_rate - exploration_rate_decay)
