export default {
  name: 'throwingPlugin',
  init(app) {
    this.app = app;
  },
  async execute() {
    throw new Error('deliberate failure for test');
  },
};
