/**
 * Sample JSX file demonstrating React component patterns
 * This file tests JSX syntax parsing and React component extraction
 */

import React, { useState, useEffect } from 'react';
import PropTypes from 'prop-types';

// Functional component with JSX
function Greeting({ name, age }) {
    return (
        <div className="greeting-container">
            <h1>Hello, {name}!</h1>
            <p>You are {age} years old.</p>
        </div>
    );
}

// Arrow function component
const Button = ({ onClick, children, disabled = false }) => {
    return (
        <button 
            className="btn" 
            onClick={onClick}
            disabled={disabled}
        >
            {children}
        </button>
    );
};

// Component with hooks
function Counter({ initialValue = 0 }) {
    const [count, setCount] = useState(initialValue);
    const [isEven, setIsEven] = useState(false);

    useEffect(() => {
        setIsEven(count % 2 === 0);
    }, [count]);

    const increment = () => {
        setCount(prevCount => prevCount + 1);
    };

    const decrement = () => {
        setCount(prevCount => prevCount - 1);
    };

    return (
        <div className="counter">
            <h2>Count: {count}</h2>
            <p>{isEven ? 'Even' : 'Odd'}</p>
            <Button onClick={increment}>+</Button>
            <Button onClick={decrement}>-</Button>
        </div>
    );
}

// Class component with JSX
class ToggleSwitch extends React.Component {
    constructor(props) {
        super(props);
        this.state = {
            isOn: props.initialState || false
        };
        this.handleToggle = this.handleToggle.bind(this);
    }

    handleToggle() {
        this.setState(prevState => ({
            isOn: !prevState.isOn
        }));
    }

    render() {
        const { isOn } = this.state;
        const { label } = this.props;
        
        return (
            <div className="toggle-switch">
                <span className="label">{label}</span>
                <button 
                    className={`toggle ${isOn ? 'on' : 'off'}`}
                    onClick={this.handleToggle}
                >
                    {isOn ? 'ON' : 'OFF'}
                </button>
            </div>
        );
    }
}

// Higher-order component
const withLoading = (WrappedComponent) => {
    return function WithLoadingComponent({ isLoading, ...props }) {
        if (isLoading) {
            return <div className="loading">Loading...</div>;
        }
        return <WrappedComponent {...props} />;
    };
};

// Custom hook
function useWindowSize() {
    const [size, setSize] = useState({
        width: window.innerWidth,
        height: window.innerHeight
    });

    useEffect(() => {
        const handleResize = () => {
            setSize({
                width: window.innerWidth,
                height: window.innerHeight
            });
        };

        window.addEventListener('resize', handleResize);
        return () => window.removeEventListener('resize', handleResize);
    }, []);

    return size;
}

// Component using custom hook
function WindowDimensions() {
    const { width, height } = useWindowSize();
    
    return (
        <div className="window-dimensions">
            <p>Window: {width} x {height}</p>
        </div>
    );
}

// Named exports
export { 
    Greeting, 
    Button, 
    Counter, 
    ToggleSwitch, 
    withLoading,
    useWindowSize,
    WindowDimensions
};

// Default export
export default Greeting;
