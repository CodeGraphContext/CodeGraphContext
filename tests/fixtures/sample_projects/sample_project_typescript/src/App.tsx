import React from 'react';
import Layout from './Layout';
import Button from '@utils/Button';
import { capitalize } from '@utils/string-helpers';
import { createUser } from '@models/user-model';

const App: React.FC = () => {
  const user = createUser(1, capitalize('admin'), 'admin@example.com');

  return (
    <Layout>
      <h2>Welcome, {user.username}</h2>
      <Button label="Click me" onClick={() => console.log('clicked')} />
    </Layout>
  );
};

export default App;
