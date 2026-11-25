#pragma once

#ifdef USE_ESP32

#include <array>
#include <cmath>
#include <cstdint>
#include <deque>
#include <string>
#include <vector>

#include "esphome/components/ble_client/ble_client.h"
#include "esphome/core/component.h"
#include "esphome/core/helpers.h"
#include "registers.h"

namespace esphome::solarlife_mppt {

/// An entity without an explicit address falls back to a name-only lookup.
static constexpr uint16_t REGISTER_ADDRESS_UNSPECIFIED = 0xFFFF;

/// One decoded register value. Exactly one field is meaningful, selected by Register::kind.
struct RegisterValue {
  float number{NAN};
  bool flag{false};
  std::string text{};
};

/// An entity that wants the values of one register.
class SolarlifeMpptEntity {
 public:
  virtual const Register *get_register() const = 0;
  virtual void on_register_value(const RegisterValue &value) = 0;
  virtual void on_write_failed() {}
};

class SolarlifeMppt : public PollingComponent, public ble_client::BLEClientNode {
 public:
  void setup() override;
  void loop() override;
  void update() override;
  void dump_config() override;
  float get_setup_priority() const override { return setup_priority::DATA; }

  void set_service_uuid(uint16_t uuid) { this->service_uuid_ = uuid; }
  void set_notify_uuid(uint16_t uuid) { this->notify_uuid_ = uuid; }
  void set_write_uuid(uint16_t uuid) { this->write_uuid_ = uuid; }
  void set_retries(uint8_t retries) { this->retries_ = retries; }
  void set_command_timeout(uint32_t timeout) { this->timeout_ = timeout; }
  void set_parameters_interval(uint32_t interval) { this->parameters_interval_ = interval; }

  void register_entity(SolarlifeMpptEntity *entity) { this->entities_.push_back(entity); }
  /// Look up a register by name only. Ambiguous names resolve to the first match.
  const Register *find_register(const char *name) const;
  /// Look up a register by name and address. Names repeat across controller blocks,
  /// so an entity must pass its address to get the block it is actually read from.
  const Register *find_register(const char *name, uint16_t address) const;

  void request_write(const Register *reg, bool on);
  void request_write_value(const Register *reg, float value);
  void request_write_index(const Register *reg, uint16_t index);
  void request_button(const Register *reg);

  void gattc_event_handler(esp_gattc_cb_event_t event, esp_gatt_if_t gatt_if,
                           esp_ble_gattc_cb_param_t *param) override;

 protected:
  enum class State : uint8_t { IDLE, WAIT_READ, WAIT_WRITE };

  struct PendingWrite {
    const Register *reg;
    float value;
    bool indexed;
  };

  void start_read_(uint16_t start, uint8_t count);
  void send_write_(const PendingWrite &write);
  void send_frame_(const uint8_t *frame, size_t length);
  void arm_timeout_();
  void on_timeout_();
  void receive_(const uint8_t *data, size_t length);
  bool frame_ready_(size_t &length);
  bool process_frame_(size_t length);
  void drop_frame_byte_();
  void handle_read_frame_(const uint8_t *data, size_t length);
  void handle_write_frame_(const uint8_t *data);
  void publish_register_(const Register &reg, const RegisterValue &value);
  RegisterValue decode_raw_(const Register &reg, uint32_t raw) const;
  std::string log_hex_(const uint8_t *data, size_t length) const;
  void publish_in_flight_();
  void reset_();

  static constexpr uint8_t DEVICE_ID = 0xFE;
  static constexpr uint8_t FUNCTION_READ_INPUT = 0x04;
  static constexpr uint8_t FUNCTION_READ_HOLDING = 0x03;
  static constexpr uint8_t FUNCTION_WRITE_STATUS = 0x05;
  static constexpr uint16_t DETAILS_START = 0x3030;
  static constexpr uint8_t DETAILS_COUNT = 41;
  static constexpr uint16_t PARAMETERS_START = 0x9021;
  static constexpr uint8_t PARAMETERS_COUNT = 12;
  static constexpr size_t MAX_FRAME = 96;
  static constexpr uint32_t TIMEOUT_ID = 0;

  std::vector<SolarlifeMpptEntity *> entities_;
  std::deque<PendingWrite> queue_;
  std::array<uint8_t, MAX_FRAME> frame_{};
  size_t frame_length_{0};

  uint16_t service_uuid_{0xFF00};
  uint16_t notify_uuid_{0xFF01};
  uint16_t write_uuid_{0xFF02};
  uint16_t notify_handle_{0};
  uint16_t write_handle_{0};
  bool write_with_response_{true};
  // Address for requests. Starts as the broadcast id and becomes the
  // controller's own id (protocol default 1) after the first response.
  uint8_t device_id_{DEVICE_ID};
  uint8_t retries_{10};
  uint8_t retries_left_{0};
  uint32_t timeout_{2000};
  uint32_t parameters_interval_{300000};
  uint32_t last_parameters_{0};
  bool parameters_due_{true};
  uint8_t parameters_failures_{0};
  std::array<uint8_t, MAX_FRAME> last_frame_{};
  size_t last_frame_length_{0};

  State state_{State::IDLE};
  uint16_t expected_start_{0};
  uint8_t expected_count_{0};
  uint8_t expected_fc_{0};
  PendingWrite in_flight_{};
  bool resync_reported_{false};
  uint8_t failed_transactions_{0};
  RegisterValue in_flight_value_{};
};

}  // namespace esphome::solarlife_mppt

#endif  // USE_ESP32
