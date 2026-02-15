import React from 'react';
import { APP_NAME } from '@shared/constants';
import { Logger } from '@shared/logger';
import Button from '@utils/Button';

interface LayoutProps {
  children: React.ReactNode;
}

const logger = new Logger('Layout');

const Layout: React.FC<LayoutProps> = ({ children }) => {
  logger.info('Rendering layout');
  return (
    <div className="layout">
      <header>
        <h1>{APP_NAME}</h1>
        <Button label="Menu" onClick={() => logger.info('menu clicked')} />
      </header>
      <main>{children}</main>
    </div>
  );
};

export default Layout;
